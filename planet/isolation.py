"""Ownership checks and a fail-closed cold inference boundary between actors."""
import copy
from .brain_errors import IsolationError

PRIVATE_KEYS={'notes','plan','thinking','memory','history','relations','strategic_assessment','decision_outcome','construction_review','economic_review','pending_decisions','decisions','modern','learning','learning_notes'}


def checked_context(state,context,decision=None):
    if context.get('state',state.id)!=state.id or context.get('private_owner',state.id)!=state.id:
        raise IsolationError('Контекст принадлежит другому государству; запрос заблокирован до отправки')
    identity=context.get('identity',{})
    if identity.get('id',state.id)!=state.id or identity.get('name',state.name)!=state.name:
        raise IsolationError('Не совпадает личность государства в контексте')
    if decision is not None and decision.get('owner',state.id)!=state.id:
        raise IsolationError('Готовое решение принадлежит другому государству; оно не будет передано модели')
    for key in ('memory','history'):
        for row in context.get(key,[]):
            if not isinstance(row,dict) or row.get('owner',state.id)!=state.id:
                raise IsolationError('Чужой владелец в частном архиве '+key)
    for item in context.get('states',[]):
        if any(key in item for key in PRIVATE_KEYS): raise IsolationError('В публичном списке стран обнаружены чужие частные поля')
    for message in context.get('messages',[]):
        if message.get('sender')!=state.id and message.get('recipient') not in (state.id,'all'): raise IsolationError('В контекст попало чужое частное письмо')
    for event in context.get('events',[]):
        if 'visible_to' in event and state.id not in event['visible_to']: raise IsolationError('В контекст попало чужое частное событие')
    result=dict(context)
    result['private_owner']=state.id
    result['identity']=dict(id=state.id,name=state.name)
    return result


class StrictIsolation:
    def bind_actor(self,actor):
        actor=str(actor)
        if actor!=getattr(self,'current_actor',None):
            self.current_actor=actor
            # No prompt/response cache exists here. Only non-content capability limits persist.
            self.active=None

    def prepare_isolated_model(self,model):
        actor=getattr(self,'current_actor',None) or '__service__'
        desired=int(self.config.get('context_window',98304))
        load_signature=(self.config.get('host'),desired)
        if load_signature!=self.load_signature:
            self.load_limits.clear(); self.load_signature=load_signature
        listing=self.request('/api/v1/models')['models']
        info=next((m for m in listing if m['key']==model or any(i['id']==model for i in m.get('loaded_instances',[]))),None)
        if info is None or info.get('type')!='llm': raise IsolationError('Для изолированного запроса нужна доступная текстовая модель')
        desired=min(desired,self.load_limits.get(info['key'],desired),info.get('max_context_length') or desired)
        signature=(self.config.get('host'),info['key'],actor,desired)
        available={instance['id'] for m in listing for instance in m.get('loaded_instances',[])}
        if self.isolated_signature==signature and self.loaded_instance in available:
            return self.loaded_instance,desired
        # At the first managed use, retire existing instances of the selected model.
        # On subsequent actor changes, retire our tracked instance; never reuse its KV state.
        to_unload=set()
        if self.loaded_instance and self.loaded_instance in available: to_unload.add(self.loaded_instance)
        to_unload.update(instance['id'] for instance in info.get('loaded_instances',[]))
        previous_owner=self.isolated_owner
        for instance in to_unload:
            try: self.request('/api/v1/models/unload',dict(instance_id=instance))
            except Exception as exc: raise IsolationError('Не удалось выгрузить предыдущий контекст. Новый запрос не отправлен: '+str(exc)) from exc
        if to_unload:
            after=self.request('/api/v1/models')['models']
            remaining={instance['id'] for m in after for instance in m.get('loaded_instances',[])}
            if to_unload & remaining: raise IsolationError('Сервер ещё держит предыдущий экземпляр. До его выгрузки новый запрос заблокирован')
        self.loaded_instance=None; self.loaded_key=None; self.isolated_signature=None; self.isolated_owner=None
        self.emit('isolation','Контекст предыдущего участника выгружен; готовим чистый экземпляр',previous_actor=previous_owner,next_actor=actor,unloaded_instances=len(to_unload))
        try:
            loaded=self.request('/api/v1/models/load',dict(model=info['key'],context_length=desired,flash_attention=True,echo_load_config=True))
        except Exception as exc:
            from .brain import context_error
            message=str(exc).lower()
            if desired>2048 and (context_error(exc) or 'insufficient' in message and ('memory' in message or 'resources' in message)):
                self.load_limits[info['key']]=max(2048,int(desired*.65))
                self.emit('status',f'Сервер отказал в окне {desired} по памяти; пробуем {self.load_limits[info["key"]]} токенов. Запрошенное в настройках окно {self.config.get("context_window")} сохранено.')
                return self.prepare_isolated_model(info['key'])
            raise IsolationError('Не удалось загрузить чистый экземпляр: '+str(exc)) from exc
        actual=loaded.get('load_config',{}).get('context_length')
        if not isinstance(actual,int) or actual<=0: raise IsolationError('Сервер не подтвердил окно чистого экземпляра; запрос не отправлен')
        self.loaded_instance=loaded['instance_id']; self.loaded_key=info['key']; self.isolated_owner=actor
        if actual<desired: self.load_limits[info['key']]=actual
        self.isolated_signature=(self.config.get('host'),info['key'],actor,min(desired,actual))
        self.emit('isolation','Чистый экземпляр готов',actor=actor,model=info['key'],context_window=actual)
        return self.loaded_instance,min(desired,actual)
