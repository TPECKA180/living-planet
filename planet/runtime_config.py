"""One-time migration of old response limits; retain user choices made after migration."""
def upgrade_config(config):
    changed=False
    if config.get('runtime_patch') not in ('6.8','6.8.2','6.8.3','6.8.4','7.0'):
        config['max_tokens']=max(28000,int(config.get('max_tokens',0)))
        config['unified_execution_review']=True
        config['reflective_learning']=True
        changed=True
    if config.get('runtime_patch') not in ('6.8.2','6.8.3','6.8.4','7.0'):
        config['local_execution']=True;config['local_chronicle']=True;changed=True
    if config.get('runtime_patch')!='7.0':
        config['input_tokens']=max(28000,int(config.get('input_tokens',28000)))
        config['runtime_patch']='7.0';changed=True
    return changed
