import click
import os, shutil
import json

def get_path(path):
    path = os.path.expanduser(path)
    return os.path.abspath(path)

def general_copy(src, dst):
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    elif os.path.isfile(src):
        shutil.copy(src, dst)
    print(f'File copied from {src=} to {dst=}')

@click.group()
@click.option('--basepath', default=os.path.join(os.getcwd(), "config-pool/mac"))
@click.pass_context
def main(ctx, basepath):
    with open(os.path.join(basepath, "config.json"), 'r') as f:
        config = json.load(f)
        ctx.obj['config'] = config
        ctx.obj['basepath'] = basepath



@main.command()
@click.pass_context
def upload(ctx):
    config = ctx.obj['config']
    basepath = ctx.obj['basepath']
    for key in config.keys():
        for item in config[key]:
            src, dst = get_path(os.path.join(basepath, item['src'])), get_path(item['dst'])
            parent = os.path.dirname(src) # find parent path of src

            if not os.path.exists(parent):
                os.makedirs(parent, 0o755, True) # mkdir -p
                print(f'Parent path {parent} created')

            general_copy(dst, src)


@main.command()
@click.pass_context
def download(ctx):
    config = ctx.obj['config']
    basepath = ctx.obj['basepath']
    for key in config.keys():
        for item in config[key]:
            src, dst = get_path(os.path.join(basepath, item['src'])), get_path(item['dst'])

            # create copy for existed files
            if not os.path.exists(dst):
                parent = os.path.dirname(dst) # find parent path of dst
                os.makedirs(parent, 0o755, True) # mkdir -p
                print(f'Parent path {parent} created')
            else:
                backup = dst + '.bak'
                general_copy(dst, backup)
                print(f'Backup file {backup} created')
                os.system(f'rm -rf {dst}')
            
            general_copy(src, dst)
            

if __name__ == '__main__':
    main(obj={})
