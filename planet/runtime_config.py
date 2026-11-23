"""One-time runtime migration for portable release defaults."""


def _compact_legacy_prompt(config):
    config['compact_prompt']=True
    config.setdefault('reasoning_budget',1024)
    config['context_map_cells']=min(2048,max(128,int(config.get('context_map_cells',2048))))
    config['input_tokens']=min(72000,max(1024,int(config.get('input_tokens',24000))))


def upgrade_config(config):
    version=config.get('runtime_patch')
    if version=='8.5.3':return False
    if version in ('8.5.1','8.5.2'):
        config['runtime_patch']='8.5.3'
        config['external_console']=True
        _compact_legacy_prompt(config)
        return True
    if version=='8.5.0':
        if config.get('context_window_profile')!='v8.0.0':
            config['context_window']=262144
            config['context_window_profile']='v8.0.0'
        config['external_console']=True
        config['runtime_patch']='8.5.3'
        _compact_legacy_prompt(config)
        return True
    if version in ('7.5.1','7.5.2','7.5.3','7.5.4','7.5.5','7.5.6','7.5.7','8.0.0','8.0.1'):
        config['runtime_patch']='8.5.3'
        config['host']='http://127.0.0.1:32124/v1';config['manage_model_context']=False;config['strict_state_isolation']=False
        config['context_window']=262144;config['context_window_profile']='v8.0.0';config['external_console']=True
        config['input_tokens']=min(12000,max(1024,int(config.get('input_tokens',12000))))
        config['max_tokens']=max(110000,int(config.get('max_tokens',196608)))
        config['api_key']=''
        _compact_legacy_prompt(config)
        return True
    changed=False
    if version not in ('6.8','6.8.2','6.8.3','6.8.4','7.0','7.0.1','7.5.0','7.5.3'):
        config['max_tokens']=max(28000,int(config.get('max_tokens',0)))
        config['unified_execution_review']=True
        config['reflective_learning']=True
        changed=True
    if version not in ('6.8.2','6.8.3','6.8.4','7.0','7.0.1','7.5.0','7.5.3'):
        config['local_execution']=True;config['local_chronicle']=True;changed=True
    if version not in ('8.0.0','8.0.1','8.5.1','8.5.2'):
        config['input_tokens']=12000
        config['max_tokens']=max(196608,int(config.get('max_tokens',196608)))
        config['context_window']=262144;config['context_window_profile']='v8.0.0'
        config['host']='http://127.0.0.1:32124/v1';config['manage_model_context']=False;config['strict_state_isolation']=False;config['api_key']=''
        config['runtime_patch']='8.5.3';config['external_console']=True
        _compact_legacy_prompt(config);changed=True
    return changed
