"""One-time migration of old response limits; retain user choices made after migration."""
def upgrade_config(config):
    changed=False
    if config.get('runtime_patch') not in ('6.8','6.8.2','6.8.3','6.8.4','7.0','7.0.1','7.5.0','7.5.1'):
        config['max_tokens']=max(28000,int(config.get('max_tokens',0)))
        config['unified_execution_review']=True
        config['reflective_learning']=True
        changed=True
    if config.get('runtime_patch') not in ('6.8.2','6.8.3','6.8.4','7.0','7.0.1','7.5.0','7.5.1'):
        config['local_execution']=True;config['local_chronicle']=True;changed=True
    if config.get('runtime_patch')!='7.5.1':
        config['input_tokens']=max(56000,int(config.get('input_tokens',56000)))
        config['max_tokens']=max(196608,int(config.get('max_tokens',196608)))
        config['context_window']=max(262144,int(config.get('context_window',262144)))
        config['runtime_patch']='7.5.1';changed=True
    return changed
