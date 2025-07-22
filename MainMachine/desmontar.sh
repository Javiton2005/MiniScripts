#!/bin/zsh

echo "Desmontando la carpeta "

echo "Conectando a ${1}"

carpeta=$1
if ! [ -n "$carpeta" ]; then
  read "carpeta?Ingrese la carpeta o el servicio que desmontar: "
fi

fusermount -u ~/remoto/${carpeta}
