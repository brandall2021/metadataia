#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Parche de firewall para METADATAIA (entorno de desarrollo).
#
# El firewall del hosting (CentOS 7 / kernel 3.10) incluye reglas anti-bogon
# que DROPean el trafico hacia/desde rangos privados:
#   -A INPUT  -s 172.16.0.0/12 -j DROP     (trafico de retorno de contenedores)
#   -A OUTPUT -d 172.16.0.0/12 -j DROP     (paquetes hacia contenedores)
#
# Docker usa redes privadas (172.17.0.0/16 docker0, 172.19.0.0/16 metadato),
# por lo que sin estas excepciones el host NO puede alcanzar los contenedores
# (los contenedores SI se comunican entre si dentro del bridge).
#
# El script es idempotente: solo inserta las reglas si no existen.
# Ejecutar como root:  ./scripts/patch-firewall.sh
# Guardar en persistencia:  service iptables save   (centOS 7)
# ---------------------------------------------------------------------------

set -euo pipefail

BRIDGES=(
  "172.17.0.0/16"
  "172.19.0.0/16"
)

insert_input_established() {
  local net="$1"
  if ! iptables -C INPUT -s "$net" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null; then
    # Insertar justo despues de "-i lo -j ACCEPT"
    local pos
    pos=$(iptables -S INPUT | grep -n -- "-i lo -j ACCEPT" | head -1 | cut -d: -f1)
    iptables -I INPUT "$((pos + 1))" -s "$net" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    echo "INPUT: aceptado trafico ESTABLISHED desde $net"
  else
    echo "INPUT: ya existe regla para $net"
  fi
}

insert_output() {
  local net="$1"
  if ! iptables -C OUTPUT -d "$net" -j ACCEPT 2>/dev/null; then
    # Insertar justo despues de "-p tcp --tcp-flags SYN,RST SYN -j TCPMSS"
    local pos
    pos=$(iptables -S OUTPUT | grep -n "TCPMSS" | head -1 | cut -d: -f1)
    iptables -I OUTPUT "$((pos + 1))" -d "$net" -j ACCEPT
    echo "OUTPUT: aceptado trafico hacia $net"
  else
    echo "OUTPUT: ya existe regla para $net"
  fi
}

for net in "${BRIDGES[@]}"; do
  insert_input_established "$net"
  insert_output "$net"
done

echo "Parche aplicado. Verificar con:  curl http://localhost:8000/health"
echo "Persistir con:                    service iptables save"