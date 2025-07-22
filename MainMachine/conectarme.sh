#!/bin/zsh

echo "Conectando a ${1}"

carpeta=$1
if ! [ -n "$carpeta" ]; then
  read "carpeta?Ingrese la carpeta o el servicio al que conectarse: "
fi

if ! [ -d "$carpeta" ]
then
   mkdir ~/remoto/${carpeta}
fi

read "usuario?Ingrese el usuario: "
read "ip?Ingrese la IP o dominio: "
sshfs ${usuario}@${ip}:/ ~/remoto/${carpeta}

cd ~/remoto/$carpeta
nvim
