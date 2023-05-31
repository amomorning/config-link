# Config link

Automatically backup config file in your backup folder.

## Installation

- `click`

## Features

- **Upload**
  - `cp` file from `dst` to `src`
- **Download**
  - `mv` original file from `dst` to `dst+'bak'`
  - create `src` dir
  - create a symbolic link from `src` to `dst`

## Usage

``` bash

# clone repo
git clone https://github.com/amomorning/config-link.git
cd config-link

# write your config.json 
# for example in ~/backup/config.json

# upload
sudo python main.py --basepath "~/backup" upload

sudo python main.py --basepath "~/backup" download
```

## JSON config example

``` json
{
    "vim": [
        {
            "src": "vim/autoload",
            "dst": "~/.vim/autoload"
        },
        {
            "src": "vim/.vimrc",
            "dst": "~/.vimrc"
        }
    ]
}
```

## Backup folder structure

``` txt
~/backup
├── config.json
└── vim
    ├── .vimrc
    └── autoload
        └── plug.vim

3 directories, 2 files
```

