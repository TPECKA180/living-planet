"""One-time migration of release defaults while retaining model and token choices."""
def upgrade_config(config):
    if config.get('runtime_patch')=='8.5.1':return False
    if config.get('runtime_patch')=='8.5.0':
        if config.get('context_window_profile')!='v8.0.0':
            config['context_window']=262144
            config['context_window_profile']='v8.0.0'
        config['external_console']=True
        config['runtime_patch']='8.5.1'
        return True
    if config.get('runtime_patch') in ('7.5.1','7.5.2','7.5.3','7.5.4','7.5.5','7.5.6','7.5.7','8.0.0','8.0.1'):
        changed=True
        config['runtime_patch']='8.5.1'
        config['host']='http://127.0.0.1:32124/v1';config['manage_model_context']=False;config['strict_state_isolation']=False
        config['context_window']=262144
        config['context_window_profile']='v8.0.0'
        config['external_console']=True
        config['input_tokens']=min(int(config.get('input_tokens',12000)),12000)
        config['max_tokens']=max(110000,int(config.get('max_tokens',196608)))
        config['api_key']=''
        return changed
    changed=False
    if config.get('runtime_patch') not in ('6.8','6.8.2','6.8.3','6.8.4','7.0','7.0.1','7.5.0','7.5.3'):
        config['max_tokens']=max(28000,int(config.get('max_tokens',0)))
        config['unified_execution_review']=True
        config['reflective_learning']=True
        changed=True
    if config.get('runtime_patch') not in ('6.8.2','6.8.3','6.8.4','7.0','7.0.1','7.5.0','7.5.3'):
        config['local_execution']=True;config['local_chronicle']=True;changed=True
    if config.get('runtime_patch') not in ('8.0.0','8.0.1','8.5.1'):
        config['input_tokens']=12000
        config['max_tokens']=max(196608,int(config.get('max_tokens',196608)))
        config['context_window']=262144
        config['context_window_profile']='v8.0.0'
        config['host']='http://127.0.0.1:32124/v1';config['manage_model_context']=False;config['strict_state_isolation']=False;config['api_key']=''
        config['runtime_patch']='8.5.1';config['external_console']=True;changed=True
    return changed
