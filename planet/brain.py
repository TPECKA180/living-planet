import json
import copy
import math
import re
import time
import urllib.error
import urllib.request

from .engine import RuleError, PRICES
from .isolation import StrictIsolation,checked_context
from .brain_errors import IsolationError
from .decision_format import decision_schema
from .context import COMPACT_RULES, TINY_RULES, estimate, fit
from .deliberation import DEEP_RULES,needed_reviews,validate_assessment,narrative_fields,supplement_schema
from .intelligence import normalize_decision,validate_actions,repetitive_tail,RepeatedOutput,REVIEW_GUIDANCE,STRATEGIC_CAMPAIGN_RULES


class AutomaticRetry(RuntimeError):
    """Transient capacity/language issue; retain the turn and retry, never skip."""


def context_error(error):
    text=str(error).lower()
    return (any(word in text for word in ('context','n_ctx','контекст')) and
            any(word in text for word in ('length','exceed','overflow','limit','full','too','больш','переполн','длин'))) or any(
                word in text for word in ('prompt too long','too many tokens','out of memory','cuda out of memory','cannot truncate','failed to truncate','failed to allocate','allocation failed','cannot allocate memory')) or ('n_ctx' in text and 'n_keep' in text)

from .current_prompt import build_rules
RULES=build_rules()


def parse_json(text):
    text=re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
    if text.startswith('```'): text=re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    try: return json.loads(text)
    except json.JSONDecodeError:
        # Also accept the original four-section format, with JSON ACTIONS.
        matches=list(re.finditer(r'(?m)^\s*(THINKING|NOTES|PLAN|ACTIONS):\s*', text))
        if len(matches)==4:
            out={m.group(1).lower():text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip() for i,m in enumerate(matches)}
            out['actions']=json.loads(out['actions']); return out
        raise ValueError('Модель должна вернуть JSON или THINKING/NOTES/PLAN/ACTIONS с JSON-списком действий')


from .construction_ai import ConstructionAI
from .economic_ai import EconomicAI
from .execution_ai import ExecutionAI


class Brain(StrictIsolation,ConstructionAI,EconomicAI,ExecutionAI):
    def __init__(self,config,observer=None):
        self.config=config
        self.active=None
        self.current_actor=None; self.isolated_signature=None; self.isolated_owner=None
        self.loaded_instance=None
        self.loaded_key=None
        self.stream_usage_support={}
        self.observer=observer
        self.context_limits={}
        self.capacity_signature=None
        self.load_limits={}
        self.load_signature=None
        self.response_limits={}
        self.schema_support={}
        self.token_ratios={}
        self.current_token_ratio=2

    def emit(self,kind,text='',**data):
        if self.observer:
            try: self.observer(kind,text,**data)
            except Exception: pass

    def stream_request(self,payload):
        from .response_io import read_json,stream_lines,response_limit
        limit=response_limit(self.config)
        batch_kind=None;batch=[];batch_size=0;batch_time=time.monotonic()
        def flush():
            nonlocal batch,batch_size,batch_time
            if batch:self.emit(batch_kind,''.join(batch))
            batch=[];batch_size=0;batch_time=time.monotonic()
        def broadcast(kind,text):
            nonlocal batch_kind,batch_size
            if kind!=batch_kind:flush();batch_kind=kind
            batch.append(text);batch_size+=len(text)
            if batch_size>=512 or time.monotonic()-batch_time>=.08:flush()
        headers={'Content-Type':'application/json','Accept':'text/event-stream'}
        if self.config.get('api_key'): headers['Authorization']='Bearer '+self.config['api_key']
        req=urllib.request.Request(self.config['host'].rstrip('/')+'/chat/completions',
            data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=self.config.get('timeout',600)) as response:
                # Some compatible servers ignore stream=true. Accept their JSON.
                if 'text/event-stream' not in response.headers.get('Content-Type','').lower():
                    result=read_json(response,limit)
                    choices=result.get('choices') if isinstance(result,dict) else None
                    if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict) or not isinstance(choices[0].get('message'),dict):return result
                    message=choices[0]['message']
                    for field,kind in (('reasoning_content','reasoning'),('reasoning','reasoning'),('content','content')):
                        if isinstance(message.get(field),str): self.emit(kind,message[field])
                    return result
                fragments=[]; finish=None; usage={}; ended=False; pending=[]; recent=''; repetition_check=0
                for line in stream_lines(response,limit):
                    line=line.decode('utf-8').rstrip('\r\n')
                    if line.startswith('data:'): pending.append(line[5:].lstrip())
                    elif not line and pending:
                        data='\n'.join(pending); pending=[]
                        if data=='[DONE]': ended=True; break
                        chunk=json.loads(data)
                        if chunk.get('error'): raise RuntimeError(json.dumps(chunk['error'],ensure_ascii=False))
                        if chunk.get('usage'): usage=chunk['usage']
                        for choice in chunk.get('choices',[]):
                            delta=choice.get('delta',{})
                            reasoning=delta.get('reasoning_content') or delta.get('reasoning')
                            if isinstance(reasoning,str): broadcast('reasoning',reasoning)
                            content=delta.get('content')
                            if isinstance(content,str):
                                fragments.append(content); broadcast('content',content)
                                recent=(recent+content)[-2000:]; repetition_check+=len(content)
                                if repetition_check>=256 and self.config.get('detect_repetition',True):
                                    repetition_check=0
                                    if repetitive_tail(recent): raise RepeatedOutput(recent)
                            if choice.get('finish_reason'): finish=choice['finish_reason']; ended=True
                if not ended: raise RuntimeError('Поток LM Studio оборвался до завершения ответа; ход не применён')
                return dict(choices=[dict(message=dict(content=''.join(fragments)),finish_reason=finish or 'stop')],usage=usage)
        except (ValueError,KeyError,TypeError,IndexError,AttributeError) as exc:
            raise RuntimeError(f'Некорректный поток LM Studio; неполное решение не применено: {exc}') from exc
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'LM Studio HTTP {exc.code}: {exc.read(4096).decode(errors="replace")[:4000]}') from exc
        except (urllib.error.URLError,TimeoutError) as exc:
            raise RuntimeError(f'Ошибка потока LM Studio: {exc}') from exc
        finally:flush()

    def request(self,path,payload=None):
        from .response_io import read_json,response_limit
        headers={'Content-Type':'application/json'}
        if self.config.get('api_key'): headers['Authorization']='Bearer '+self.config['api_key']
        base=self.config['host'].rstrip('/')
        if path.startswith('/api/') and base.endswith('/v1'): base=base[:-3]
        request=urllib.request.Request(base+path,
            data=json.dumps(payload).encode('utf-8') if payload is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=self.config.get('timeout',600)) as response:
                return read_json(response,response_limit(self.config))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'LM Studio HTTP {exc.code}: {exc.read(1024).decode(errors="replace")[:500]}') from exc
        except (urllib.error.URLError,TimeoutError) as exc:
            raise RuntimeError(f'Нет ответа LM Studio: {exc}. Проверьте сервер и адрес в настройках.') from exc

    def models(self):
        return [m['id'] for m in self.request('/models')['data']]

    def prepare_model(self,model):
        """Match actual server context to the chosen window, not only prompt size."""
        if self.config.get('strict_state_isolation',False): return self.prepare_isolated_model(model)
        self.isolated_signature=None; self.isolated_owner=None
        desired=int(self.config.get('context_window',98304))
        if not self.config.get('manage_model_context',False): return model,desired
        signature=(self.config.get('host'),desired)
        if signature!=self.load_signature:
            self.load_limits.clear(); self.load_signature=signature
        listing=self.request('/api/v1/models')['models']
        info=next((m for m in listing if m['key']==model or any(i['id']==model for i in m.get('loaded_instances',[]))),None)
        if info is None: raise ValueError(f'Модель {model} не найдена в LM Studio')
        if info.get('type')!='llm': raise ValueError('Для государства нужна текстовая модель')
        maximum=info.get('max_context_length')
        desired=min(desired,self.load_limits.get(info['key'],desired))
        if maximum and desired>maximum:
            desired=maximum; self.emit('status',f'Модель поддерживает {maximum} токенов: автоматически сокращаем окно.')
        if self.loaded_key and self.loaded_key!=info['key'] and self.loaded_instance:
            if any(i['id']==self.loaded_instance for m in listing for i in m.get('loaded_instances',[])):
                self.request('/api/v1/models/unload',dict(instance_id=self.loaded_instance))
            self.loaded_instance=None; self.loaded_key=None
        instances=info.get('loaded_instances',[])
        matching=next((i for i in instances if i.get('config',{}).get('context_length',0)>=desired),None)
        if matching:
            self.loaded_instance=matching['id']; self.loaded_key=info['key']
            return matching['id'],desired
        # Reload only the selected model when its existing context is too short.
        for instance in instances:
            self.request('/api/v1/models/unload',dict(instance_id=instance['id']))
        try:
            loaded=self.request('/api/v1/models/load',dict(model=info['key'],context_length=desired,flash_attention=True,echo_load_config=True))
        except Exception as exc:
            text=str(exc).lower()
            if desired>2048 and (context_error(exc) or 'insufficient' in text and ('resources' in text or 'memory' in text)):
                reduced=max(2048,int(desired*.65)); self.load_limits[info['key']]=reduced
                self.emit('status',f'Большое окно не загрузилось. Сокращаем до {reduced} токенов и продолжаем.')
                return self.prepare_model(info['key'])
            # A rejected increase must not leave a previously loaded model gone.
            if instances:
                previous=instances[0].get('config',{}).get('context_length')
                if previous:
                    try:
                        restored=self.request('/api/v1/models/load',dict(model=info['key'],context_length=previous,flash_attention=True,echo_load_config=True))
                        self.loaded_instance=restored['instance_id']; self.loaded_key=info['key']
                    except Exception as restore_error:
                        raise RuntimeError(f'{exc}\nТакже не удалось восстановить прежнюю загрузку: {restore_error}') from exc
            raise
        actual=loaded.get('load_config',{}).get('context_length')
        if not isinstance(actual,int) or actual<=0:
            raise ValueError('Сервер не подтвердил выбранный контекст. Проверьте настройки загрузки LM Studio.')
        if actual<desired:
            self.load_limits[info['key']]=actual
            self.emit('status',f'Сервер выделил {actual} токенов. Уменьшаем размер запроса автоматически.')
        self.loaded_instance=loaded['instance_id']; self.loaded_key=info['key']
        return self.loaded_instance,min(desired,actual)

    def answer_budget(self,system,window,limit=None):
        requested=int(self.config.get('max_tokens',196608)) if limit is None else int(limit)
        available=max(256,window-estimate(system)-max(1024,int(self.config.get('input_tokens',56000)))-2048)
        return max(256,min(requested,available))

    def fit_context(self,system,context,window,output=None):
        output=output if output is not None else self.answer_budget(system,window)
        if system==RULES and estimate(system)>max(256,window-output-2048):
            system=COMPACT_RULES if estimate(COMPACT_RULES)<=max(256,window-output-2048) else TINY_RULES
        from .context import ContextCapacityError
        ratio=getattr(self,'current_token_ratio',2)
        try:return fit(system,context,window,output,bytes_per_token=ratio,input_budget=int(self.config.get('input_tokens',56000)))
        except ContextCapacityError:
            # 28000 is the desired user-data budget, not permission to erase facts.
            result=fit(system,context,window,output,bytes_per_token=ratio)
            result['context_info']['requested_user_input_tokens']=int(self.config.get('input_tokens',56000))
            result['context_info']['expanded_for_actionable_data']=True
            return result

    def complete(self,system,context,model):
        from .response_io import ResponseTooLarge
        if not model: raise ValueError('Выберите модель в настройках (F2)')
        context=dict(context); response_schema=context.pop('_response_schema',None)
        signature=(self.config.get('host'),self.config.get('context_window'),self.config.get('manage_model_context'),self.config.get('max_tokens'),self.config.get('input_tokens',56000))
        if signature!=self.capacity_signature:
            self.context_limits.clear(); self.response_limits.clear(); self.token_ratios.clear(); self.stream_usage_support.clear(); self.capacity_signature=signature
        model,window=self.prepare_model(model)
        self.current_token_ratio=self.token_ratios.get(model,2) if self.config.get('calibrate_context',False) else 2
        if self.config.get('strict_state_isolation',False) and self.isolated_owner!=(getattr(self,'current_actor',None) or '__service__'):
            raise IsolationError('Владелец экземпляра модели не совпадает с участником запроса')
        window=min(window,self.context_limits.get(model,window))
        attempts=max(1,int(self.config.get('context_retry_attempts',8)))
        repair=None;envelope_error=None
        for attempt in range(attempts):
            output=self.answer_budget(system,window,self.response_limits.get(model))
            actual_system=system
            desired_input=max(1024,int(self.config.get('input_tokens',56000)))
            # The same context window holds system + user data + model output.
            # Reserve the requested factual input BEFORE a generous answer cap.
            if system==RULES and estimate(system)+min(desired_input,window//2)+1024>window:
                actual_system=COMPACT_RULES if estimate(COMPACT_RULES)+1024<window else TINY_RULES
            output=min(output,max(256,window-estimate(actual_system)-desired_input-2048))
            system_budget=max(256,window-output-2048)
            if estimate(system)>system_budget:
                actual_system=(COMPACT_RULES if estimate(COMPACT_RULES)<=system_budget else TINY_RULES) if system==RULES else 'Ответь только JSON на русском. Выполни задачу из task; сохрани ключи и технические значения.'
                if system!=RULES: payload_context=dict(context,task=system)
                else: payload_context=context
            else: payload_context=context
            if response_schema and not (self.config.get('structured_reviews',True) and self.schema_support.get(model,True)):
                payload_context=dict(payload_context,output_contract=response_schema.get('json_schema',{}).get('schema',response_schema))
            if repair:
                payload_context=dict(payload_context,format_correction=repair)
                actual_system+='\nПредыдущий ответ не разобран как JSON. Исправь формат по format_correction. Верни один JSON-объект без Markdown, рассуждений вне объекта и постороннего текста.'
            from .context import ContextCapacityError
            try:fitted=self.fit_context(actual_system,payload_context,window,output)
            except ContextCapacityError as exc:
                if output>1024:
                    self.response_limits[model]=max(1024,output//2)
                    self.emit('status','Сохраняем данные для действий; уменьшаем резерв ответа и повторяем подготовку запроса.')
                    continue
                raise AutomaticRetry(str(exc)) from exc
            self.emit('request_start',f'{self.active or "Менеджер / служебный запрос"} · окно {window}, вход до {desired_input} + правила, ответ до {output} из запрошенных {int(self.config.get("max_tokens",196608))} токенов · попытка {attempt+1}',window=window,requested_output=int(self.config.get('max_tokens',196608)),actual_output=output,estimated_input=fitted['context_info']['estimated_input_tokens'])
            if fitted['context_info']['trimmed']:
                self.emit('status','Контекст сокращён только для запроса: '+json.dumps(fitted['context_info']['trimmed'],ensure_ascii=False))
            payload=dict(model=model,messages=[dict(role='system',content=actual_system),
                dict(role='user',content=json.dumps(fitted,ensure_ascii=False,separators=(',',':')))],
                temperature=self.config.get('temperature',.7),max_tokens=output,stream=self.config.get('stream',True))
            if payload['stream'] and self.stream_usage_support.get(model,True):payload['stream_options']=dict(include_usage=True)
            if response_schema and self.config.get('structured_reviews',True) and self.schema_support.get(model,True): payload['response_format']=response_schema
            try:
                response=self.stream_request(payload) if payload['stream'] else self.request('/chat/completions',payload)
            except ResponseTooLarge as exc:
                repair=dict(error=str(exc),instruction='Сократи повторяющиеся объяснения, сохрани полный JSON, конкретные приказы, память и стратегию. Не дублируй рассуждения.')
                self.emit('status','Ответ превышает защитный предел. Повторяем текущий запрос; черновик не применяется.')
                continue
            except RepeatedOutput as exc:
                repair=dict(error=str(exc),previous_response=exc.preview,instruction='Не повторяй абзацы. Досье:2–4 предложения, разбор:конкретные краткие выводы, один полный JSON.')
                self.emit('status','Обнаружено зацикливание текста. Повторяем только текущий запрос, не увеличивая бессмысленный повтор и не применяя черновик.')
                continue
            except RuntimeError as exc:
                if 'stream_options' in payload and 'stream_options' in str(exc).lower():
                    self.stream_usage_support[model]=False
                    self.emit('status','Сервер не поддерживает статистику потока; повторяем без stream_options. Решение и входной бюджет сохранены.')
                    continue
                if 'response_format' in payload and any(term in str(exc).lower() for term in ('schema','grammar','response_format','not supported')):
                    self.schema_support[model]=False
                    self.emit('status','Сервер не принял JSON-схему дополнения. Используем уточнение с обычной проверкой структуры.')
                    continue
                if not context_error(exc): self.emit('error',str(exc)); raise
                self.token_ratios.pop(model,None); self.current_token_ratio=2
                window=max(2048,int(window*.55)); self.context_limits[model]=window
                self.emit('status',f'Переполнение: сокращаем запрос до бюджета {window} токенов и повторяем тот же ход.')
                continue
            choices=response.get('choices') if isinstance(response,dict) else None
            if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict) or not isinstance(choices[0].get('message'),dict):
                envelope_error='Сервер вернул ответ без choices/message; повторяем запрос, не изменяя день.'
                self.emit('status',envelope_error);continue
            envelope_error=None
            usage=response.get('usage') or {}
            if not isinstance(usage,dict):usage={}
            self.emit('request_end','Ответ получен. '+json.dumps(usage,ensure_ascii=False))
            prompt_tokens=usage.get('prompt_tokens')
            if self.config.get('calibrate_context',False) and type(prompt_tokens) is int and prompt_tokens>0:
                byte_count=sum(len(m['content'].encode('utf-8')) for m in payload['messages'])
                ratio=max(2,min(3.5,byte_count/(prompt_tokens*1.45)))
                self.token_ratios[model]=min(self.token_ratios.get(model,3.5),ratio)
            choice=response['choices'][0]
            if choice.get('finish_reason')=='length':
                larger=self.answer_budget(actual_system,window,min(output*2,int(self.config.get('max_tokens',196608))))
                if larger>output:
                    self.response_limits[model]=larger
                    self.emit('status',f'Ответ обрезан. Выделяем до {larger} токенов ответа, сохраняем входной бюджет и повторяем без применения неполного решения.')
                    continue
                repair=dict(error='Ответ достиг предельного бюджета; неполный JSON не применён.',instruction='Верни полный JSON компактнее, без повторов. Сохрани все обязательные поля, конкретные приказы и собственную стратегию. notes/plan=null допустимы для сохранения прежних. Не повторяй весь прежний ответ.')
                self.emit('status','Достигнут доступный предел ответа. Уточняем компактную форму JSON с тем же входным бюджетом; мир не изменён.')
                continue
            content=choice['message'].get('content')
            if not isinstance(content,str):
                repair=dict(error='Модель вернула пустой/нетекстовый ответ',instruction='Верни полный JSON-объект в content, без вызовов инструментов.')
                self.emit('status','Пустой ответ: повторяем с уточнением формата, не применяя решение.');continue
            try:
                parsed=parse_json(content)
                if not isinstance(parsed,dict): raise ValueError('Верхний уровень должен быть JSON-объектом, не списком/строкой')
                return parsed
            except (ValueError,TypeError) as exc:
                repair=dict(error=str(exc),previous_response=content[-12000:])
                self.emit('status','Ответ не является корректным JSON. Уточняем формат и повторяем запрос; день не пропущен.')
                continue
        if envelope_error:raise AutomaticRetry(envelope_error)
        if repair: raise AutomaticRetry('Ответы всё ещё не являются JSON после уточнений. Автоматический повтор через 5 секунд; ход и готовые решения сохранены.')
        raise AutomaticRetry('Сервер всё ещё сообщает о переполнении. Контекст уже сокращён; автоматический повтор через 5 секунд, ход сохранён.')

    @staticmethod
    def russian(text):
        # Ignore technical identifiers, action/terrain names and URLs.
        clean=re.sub(r'https?://\S+|state_\d+|\b(?:food|resource|metal|science|matter|money|army|lab|mine|navigation|agriculture|trade|accept_trade|transfer|settle|alliance|migrate|move|explore|hold|policy|relationship|declare_war|peace|embargo|reserve_money|unit_limit|recruit|castle|tavern|arsenal|scout|builder|build|unit|upgrade|research|do_nothing|grass|forest|mountain|water|JSON|LM Studio)\b','',text,flags=re.I)
        russian=len(re.findall(r'[А-Яа-яЁё]',clean)); latin=len(re.findall(r'[A-Za-z]',clean))
        if latin>=4 and (russian==0 or russian/(russian+latin)<.65): return False
        for sentence in re.split(r'[.!?\n]',clean):
            if len(re.findall(r'\b[A-Za-z]{2,}\b',sentence))>=4 and not re.search(r'[А-Яа-яЁё]',sentence): return False
        return True

    def russify(self,result,model,manager=False):
        if not manager and result.get('owner') is not None and result['owner']!=self.current_actor: raise IsolationError('Перевод чужого готового решения заблокирован')
        result=copy.deepcopy(result)
        fields={key:result[key] for key in (('title','description') if manager else ('thinking','notes','plan')) if isinstance(result.get(key),str)}
        if not manager:
            fields.update(narrative_fields(result))
            fields.update({f'diplomacy.{i}.text':msg['text'] for i,msg in enumerate(result.get('diplomacy',[])) if isinstance(msg,dict) and isinstance(msg.get('text'),str)})
            for i,action in enumerate(result.get('actions',[])):
                args=action.get('args',{}) if isinstance(action,dict) else {}
                for key in ('reason','memo','grievance'):
                    if isinstance(args.get(key),str): fields[f'actions.{i}.args.{key}']=args[key]
        bad={key:value for key,value in fields.items() if not self.russian(value)}
        if not bad: return result
        prompt='Ты переводчик вымышленной стратегической игры. Переведи все значения texts строго на русский, сохрани смысл, характер и политический обман. Верни только JSON-объект: те же ключи texts и переведённые строки значений, без обёртки texts. Технические id не меняй.'
        translation_error=None
        for _ in range(2):
            self.emit('status','Обнаружен английский текст: выполняем перевод на русский, игровые действия не меняются.')
            properties={key:dict(type='string',minLength=1,maxLength=64000) for key in bad}
            schema=dict(type='json_schema',json_schema=dict(name='russian_fields',strict=True,schema=dict(type='object',properties=properties,required=list(properties),additionalProperties=False)))
            translated=self.complete(prompt,dict(texts=bad,correction=translation_error,_response_schema=schema),model)
            if isinstance(translated,dict) and all(isinstance(translated.get(key),str) and translated[key].strip() and self.russian(translated[key]) for key in bad):
                for key in bad:
                    target=result; parts=key.split('.')
                    for part in parts[:-1]: target=target[int(part)] if isinstance(target,list) else target[part]
                    target[parts[-1]]=translated[key]
                return result
            translation_error=dict(error='Верни все исходные ключи верхнего уровня без обёртки texts и только русский перевод.',previous=translated)
        raise AutomaticRetry('Модель не исправила язык. Ход сохранён; автоматически повторим запрос на русском через 5 секунд.')

    def think(self,state,context):
        if self.active is not None: raise RuntimeError('Одновременно разрешён только один Brain')
        context=checked_context(state,context); self.bind_actor(state.id)
        self.active=state.id
        try:
            model=self.config.get('state_models',{}).get(state.id) or self.config.get('model')
            base_context=dict(context)
            if self.config.get('deep_strategy',False):
                base_context['required_relation_reviews']=needed_reviews(context)
                base_context['strategic_schema']='strategic_assessment: objective, horizon_days3..10, alternatives3..5[{mode,gain,risk,opponent_response}], chosen, risk_limits{min_food_days,money_reserve,stop_condition}, rival_plan{partner,method,phase,leverage,public_position,private_intent,trigger,fallback}, success_metric. relation_reviews: оценки required_relation_reviews. Все объяснения по-русски, краткие проверяемые выводы.'
            if self.config.get('structured_primary',False): base_context['_response_schema']=decision_schema(state,context,PRICES,self.config.get('deep_strategy',False),strict_actions=self.config.get('decision_compiler',False))
            request_context=base_context
            for attempt in range(max(1,int(self.config.get('decision_repair_attempts',3)))):
                try:
                    result=self.complete(RULES,request_context,model)
                    if self.config.get('decision_compiler',False):
                        result=normalize_decision(result,context)
                        try:validate_actions(result,context)
                        except (ValueError,TypeError,KeyError,AttributeError) as exc:
                            if not self.config.get('local_execution',False):raise
                            result.setdefault('action_validation_warnings',[]).append(str(exc))
                            self.emit('status','Есть замечание к отдельному приказу: '+str(exc)+'. Сохраняем готовый разбор; приказы проверяются по порядку обычным движком без повторной генерации всего решения.')
                    self.validate_decision(result,state,context)
                    if self.config.get('strict_state_isolation',False) or self.config.get('structured_primary',False): result['owner']=state.id; result['origin_patch']='7.5.1'
                    deep_complete=False
                    if self.config.get('deep_strategy',False):
                        try: validate_assessment(result,state,base_context); deep_complete=True
                        except (ValueError,TypeError,KeyError,AttributeError) as exc:
                            result['strategic_review_required']=str(exc)
                            self.emit('status',('Разбор неполный; замечание сохранено для следующего хода: ' if self.config.get('local_execution',False) else 'Основное решение готово. Сохраняем его; отдельно уточним разбор: ')+str(exc))
                    result=self.russify(result,model)
                    if deep_complete:
                        try: validate_assessment(result,state,base_context)
                        except ValueError as exc: deep_complete=False; result['strategic_review_required']=str(exc)
                    if deep_complete: result['relation_review_attempted']=context['day']; result['strategic_review_completed']=context['day']
                    if not self.config.get('local_execution',False) and result.get('origin_patch') in ('5.3','6.0','6.1','6.2','6.3','6.4','6.5','6.6','6.7','6.8','6.8.1','6.8.2','6.8.3','6.8.4','7.0','7.0.1','7.5.0','7.5.1'):
                        try: result=self.compile_construction(context,result)
                        except ValueError as exc:
                            result['construction_review_required']=str(exc)
                            self.emit('status','Основной ответ сохранится; уточним только стройку: '+str(exc))
                    if not self.config.get('local_execution',False) and result.get('origin_patch') in ('6.1','6.2','6.3','6.4','6.5','6.6','6.7','6.8','6.8.1','6.8.2','6.8.3','6.8.4','7.0','7.0.1','7.5.0','7.5.1'):
                        try: result=self.compile_economy(state,context,result)
                        except (ValueError,TypeError,KeyError) as exc:
                            result['economic_review_required']=str(exc)
                            self.emit('status','Основной ответ сохранится; уточним казначейские приказы: '+str(exc))
                    return result
                except (ValueError,TypeError,KeyError,AttributeError) as exc:
                    self.emit('status','Исправляем структуру решения: '+str(exc)+'. Готовые решения других стран сохранены.')
                    request_context=dict(base_context,decision_correction=dict(error=str(exc),instruction='Верни полный исправленный ответ: thinking, notes, plan, diplomacy 1–8 сообщений, actions до12; при strategic_schema добавь стратегический разбор и требуемые досье. Используй только известных адресатов.',previous=result if 'result' in locals() else None))
            raise AutomaticRetry('Не удалось исправить структуру решения за серию уточнений. Новый автоматический повтор через 5 секунд; день не пропущен.')
        finally: self.unload()

    def validate_decision(self,result,state,context):
        if not isinstance(result,dict): raise ValueError('Нужен JSON-объект решения')
        if result.get('owner',state.id)!=state.id: raise ValueError('Ответ должен принадлежать только собственной стране '+state.id)
        if self.config.get('reflective_learning',False):
            text=result.get('learning_notes')
            if text is None and not context.get('learning',{}).get('notes'):raise ValueError('Нужна первая learning_notes: проверяемая стратегия, гипотеза, действия, риск и критерий результата')
            if text is not None and (not isinstance(text,str) or not 30<=len(text.strip())<=8000):raise ValueError('learning_notes: содержательная стратегия 30–8000 символов либо null для сохранения прежней')
        for key in ('thinking','notes','plan'):
            inherited=key in ('notes','plan') and result.get(key)==context.get(key)
            if not isinstance(result.get(key),str) or not result[key].strip() or len(result[key])>64000 and not inherited:
                raise ValueError(f'Некорректное поле {key}')
        if not isinstance(result.get('actions'),list) or len(result['actions'])>12:
            raise ValueError('Нужен список actions: не более 12 действий')
        if any(not isinstance(a,dict) for a in result['actions']): raise ValueError('Каждое действие должно быть объектом')
        diplomacy=result.get('diplomacy')
        if not isinstance(diplomacy,list) or not 1<=len(diplomacy)<=8: raise ValueError('Общение обязательно: нужен diplomacy с 1–8 сообщениями')
        known={other['id'] for other in context.get('states',[])}
        for msg in diplomacy:
            if not isinstance(msg,dict) or not isinstance(msg.get('to'),str) or (msg['to']!='all' and (msg['to']==state.id or msg['to'] not in known)):
                raise ValueError('Неверный адресат сообщения')
            if not isinstance(msg.get('text'),str) or not 1<=len(msg['text'].strip())<=4000: raise ValueError('Неверный текст сообщения')
        for action in result['actions']:
            if not isinstance(action.get('args',{}),dict): raise ValueError('args действия должен быть объектом')
            if action.get('type',action.get('action')) not in PRICES: raise ValueError('Неизвестный type действия: '+str(action.get('type',action.get('action'))))
        return result

    def unload(self):
        # End the local request scope. StrictIsolation unloads the native model
        # instance before the next actor; same-actor repairs reuse this instance.
        self.active=None

    def review_strategy(self,state,context,decision):
        """Never reroll valid public actions to fix a private analysis section."""
        context=checked_context(state,context,decision); self.bind_actor(state.id)
        result=copy.deepcopy(decision); base=dict(context,required_relation_reviews=needed_reviews(context))
        try:
            validate_assessment(result,state,base)
            result['strategic_review_completed']=context['day']; result['relation_review_attempted']=context['day']; result.pop('strategic_review_required',None)
            return result
        except (ValueError,TypeError,KeyError,AttributeError) as exc: error=str(exc)
        assessment_needed=True
        try:
            validate_assessment(result,state,dict(base,required_relation_reviews=[])); assessment_needed=False
        except (ValueError,TypeError,KeyError,AttributeError): pass
        peers=base['required_relation_reviews']
        prompt='''Ты стратегический советник того же вымышленного государства. Основное решение уже сохранено: не меняй actions, notes, plan и diplomacy. Дополни только проверяемый стратегический разбор и нужные досье. Используй полный переданный контекст, actual_decision и strategic_brief. Сохрани характер и корыстную цель превосходства. Нужны минимум3 РАЗНЫХ альтернативы; при общей границе/войне обязательно war, даже если он отклонён. Для каждой — выгода, риск и ответ противника. Коварство конкретное: рычаг, публичная позиция, частная цель, триггер усиления давления и запасной вариант. Не выдумывай скрытые бюджеты, войны и преимущества. В risk_limits укажи реальные числовые пределы. Только JSON по заданной схеме. Все пояснения по-русски. Это краткие выводы, а не внутренняя цепочка рассуждений.'''+DEEP_RULES
        prompt+=STRATEGIC_CAMPAIGN_RULES
        model=self.config.get('state_models',{}).get(state.id) or self.config.get('model'); previous=self.active; self.active='Стратегический разбор · '+state.name
        prompt+=REVIEW_GUIDANCE+'\nТВОЯ СТРАНА: '+state.name+' ('+state.id+'). Не становись советником соперника и не предлагай ослабить собственную страну. Исправляй только разделы, перечисленные в схеме; остальное уже сохранено.'
        try:
            for _ in range(max(1,int(self.config.get('decision_repair_attempts',3)))):
                fields=None
                if assessment_needed and isinstance(result.get('strategic_assessment'),dict):
                    if 'альтернатив' in error.lower() or 'chosen' in error: fields={'alternatives','chosen'}
                    elif any(key in error for key in ('risk_limits','money_reserve','min_food_days','stop_condition')): fields={'risk_limits'}
                    elif 'rival_plan' in error or 'соперника' in error: fields={'rival_plan'}
                rivals=[s['id'] for s in context.get('states',[]) if s['id']!=state.id and not s.get('eliminated')]
                schema=supplement_schema(peers,assessment_needed,fields,rivals)
                private_only='перепутана собственная' in error and isinstance(result.get('strategic_assessment',{}).get('rival_plan'),dict)
                task_prompt=prompt
                if private_only:
                    plan_schema=schema['json_schema']['schema']['properties']['strategic_assessment']['properties']['rival_plan']
                    plan_schema['properties']={key:value for key,value in plan_schema['properties'].items() if key=='private_intent'}; plan_schema['required']=['private_intent']
                    target=result['strategic_assessment']['rival_plan'].get('partner'); target_name=next((s['name'] for s in context.get('states',[]) if s['id']==target),str(target))
                    task_prompt+='\nСЕЙЧАС ИСПРАВЬ ТОЛЬКО private_intent: объект нашей политики — '+target_name+' ('+str(target)+'). В этой фразе не упоминай нашу страну '+state.name+' вообще; собственная выгода уже записана в objective. Опиши, что мы хотим сделать с выбранным соперником.'
                payload=dict(base,identity=dict(id=state.id,name=state.name),actual_decision=result,section_error=error,_response_schema=schema)
                try:
                    update=self.complete(task_prompt,payload,model)
                    for key in ('strategic_assessment','relation_reviews'):
                        if key in update:
                            if key=='relation_reviews' and isinstance(update[key],dict): result[key]={**(result.get(key,{}) if isinstance(result.get(key),dict) else {}),**update[key]}
                            elif key=='strategic_assessment' and isinstance(update[key],dict):
                                allowed={k:v for k,v in update[key].items() if fields is None or k in fields}
                                if private_only and isinstance(allowed.get('rival_plan'),dict): allowed['rival_plan']={**result[key]['rival_plan'],**{k:v for k,v in allowed['rival_plan'].items() if k=='private_intent'}}
                                result[key]={**(result.get(key,{}) if isinstance(result.get(key),dict) else {}),**allowed}
                            else: result[key]=update[key]
                    validate_assessment(result,state,base)
                    result=self.russify(result,model); validate_assessment(result,state,base)
                    result['strategic_review_completed']=context['day']; result['relation_review_attempted']=context['day']; result.pop('strategic_review_required',None)
                    return result
                except (ValueError,KeyError,TypeError,AttributeError) as exc:
                    error=str(exc); self.emit('status','Уточняем только стратегическое дополнение: '+error)
            raise AutomaticRetry('Разбор требует уточнения; основной ответ сохранён и не будет запрашиваться заново. Повтор через 5 секунд.')
        finally: self.active=previous

    def review_relationships(self,state,context,decision):
        """A separate private review, checkpointed by Runner before execution."""
        context=checked_context(state,context,decision); self.bind_actor(state.id)
        decision=copy.deepcopy(decision)
        if decision.get('relation_review_attempted')==context['day']: return decision
        existing=decision.get('relation_reviews',{})
        explicit={a.get('args',{}).get('partner') for a in decision.get('actions',[]) if a.get('type')=='relationship' and a.get('args',{}).get('memo')}
        needed={}
        for peer,record in context.get('relations',{}).items():
            reviewed=record.get('last_review_day')
            significant=any(f.get('day') is not None and reviewed is not None and f['day']>=reviewed and f['kind'] in ('war','betrayal','trade','embargo','territory_loss') for f in record.get('facts',[]))
            if peer not in explicit and peer not in existing and (not record.get('memo') or reviewed is None or context['day']-reviewed>=5 or significant): needed[peer]=record
        decision['relation_review_attempted']=context['day']
        if not needed: return decision
        prompt='''Ты — личный дипломатический советник того же вымышленного государства. Сохраняй его характер и корыстные цели. Оцени каждого партнёра из partners: стоит ли дружить, торговать, опасаться, есть ли подтверждённая обида и выгодна ли война. Не выдумывай факты. Красивые обещания не равны гарантированному доходу. Сопоставь собственную экономику и переписку с пользой партнёра. Незнакомому партнёру допустима осторожная нейтральная оценка, но не пустое досье.
Только JSON: {"reviews":{"state_N":{"trust":0,"stance":"neutral","trade_policy":"normal","memo":"Краткая личная оценка и расчёт по-русски"}}}.
trust — целое -100..100; stance — neutral/friend/rival/enemy; trade_policy — normal/preferred/avoid. memo — 1–3 предложения строго по-русски. В ответе обязательно все ключи partners. Это частные мнения, не объявления войны и не изменения чужих ресурсов.'''
        payload=dict(day=context['day'],state=state.id,notes=decision.get('notes',state.notes),plan=decision.get('plan',state.plan),
                     economy=context.get('economy',{}),partners=needed,
                     messages=[m for m in context.get('messages',[]) if m['sender'] in needed or m['recipient'] in needed][-35:])
        model=self.config.get('state_models',{}).get(state.id) or self.config.get('model')
        previous=self.active; self.active='Досье · '+state.name
        try:
            raw=self.complete(prompt,payload,model)
            values=raw.get('reviews',{}) if isinstance(raw,dict) else {}
            updates={}
            for peer in needed:
                item=values.get(peer)
                if not isinstance(item,dict): continue
                if type(item.get('trust')) is not int or not -100<=item['trust']<=100: continue
                if item.get('stance') not in ('neutral','friend','rival','enemy') or item.get('trade_policy') not in ('normal','preferred','avoid'): continue
                if not isinstance(item.get('memo'),str) or not item['memo'].strip() or len(item['memo'])>4000: continue
                updates[peer]={key:item[key] for key in ('trust','stance','trade_policy','memo')}
            actions=[dict(type='relationship',args=dict(partner=peer,**item)) for peer,item in updates.items()]
            local=self.russify(dict(actions=actions),model)
            for action in local['actions']:
                args=action['args']; peer=args['partner']; existing[peer]={k:v for k,v in args.items() if k!='partner'}
            decision['relation_reviews']=existing
            if len(updates)<len(needed): self.emit('status','Часть оценок отношений не получена. Сохраняем прежние профили; игровой ход продолжится.')
        except (ValueError,KeyError,TypeError,AttributeError):
            self.emit('status','Ответ для досье некорректен. Прежняя оценка сохранена; игровой ход продолжится.')
        finally: self.active=previous
        return decision

    def manager(self,world):
        self.bind_actor('__manager__')
        correction=None
        for _ in range(max(1,int(self.config.get('decision_repair_attempts',3)))):
            try: return self._manager_once(world,correction)
            except (ValueError,TypeError,KeyError,AttributeError,RuleError) as exc:
                correction=str(exc)
                self.emit('status','Уточняем некорректное событие менеджера: '+correction)
        raise AutomaticRetry('Событие менеджера не прошло проверку; повтор через 5 секунд без пропуска дня.')

    def _manager_once(self,world,correction=None):
        prompt='''Ты менеджер истории, не государство. Выбери одно ограниченное событие. Только JSON:
{"event":"harvest|drought|fair|epidemic|earthquake|peace","target":null,"title":"Название","description":"Краткая хроника на русском","expand":false}.
target: null (все) или state_N. harvest +50 еды, drought -40 еды до 0, fair +80 денег,
epidemic убивает одного жителя, earthquake разрушает одно здание, peace только хроника.
expand=true расширяет мир 128→256→512, старые координаты сохраняются. Не меняй память государств.
События обогащают историю; избегай постоянных катастроф и необоснованных расширений.'''
        result=self.complete(prompt,dict(format_correction=correction,day=world.day,size=world.size,states=[dict(id=s.id,stocks=s.stocks,territory=len(world.positions(s.id))) for s in world.states],events=world.events[-10:]),self.config.get('manager_model') or self.config['model'])
        if result.get('event') not in ('harvest','drought','fair','epidemic','earthquake','peace'): raise RuleError('Неверное событие менеджера')
        if result.get('target') is not None and result['target'] not in {s.id for s in world.states if not s.eliminated}: raise RuleError('target должен быть null или id действующего государства')
        if type(result.get('expand')) is not bool: raise RuleError('expand должен быть true/false')
        for k in ('title','description'):
            if not isinstance(result.get(k),str) or not result[k].strip(): raise RuleError('Нет текста события')
        return self.russify(result,self.config.get('manager_model') or self.config['model'],manager=True)

