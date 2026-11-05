#!/system/bin/sh
set -eu
umask 077
MODDIR=$(CDPATH= cd "${0%/*}/.." && pwd)
DATA=/data/adb/honksu
PROC_ROOT=/proc
HOT_TRASH_ROOT=/data/adb/ksu/hot_install_trash
if [ "${HONKSU_TEST_MODE:-0}" = 1 ]; then
  DATA=${HONKSU_TEST_DATA:?test data directory required}
  PROC_ROOT=${HONKSU_TEST_PROC_ROOT:-/proc}
  HOT_TRASH_ROOT=${HONKSU_TEST_HOT_TRASH_ROOT:-$DATA/hot-install-trash}
fi
CORE=$MODDIR/bin/honk-core
CORE_CHECKED=0

fail() { printf '%s\n' "$*" >&2; exit 1; }
b64() { base64 | tr -d '\n'; }
decode() { printf '%s' "$1" | base64 -d; }
value() { cat "$DATA/settings/$1"; }
put() {
  printf '%s\n' "$2" > "$DATA/settings/.$1.$$"
  mv -f "$DATA/settings/.$1.$$" "$DATA/settings/$1"
}
init() {
  [ "${HONKSU_TEST_MODE:-0}" = 1 ] || [ "$(id -u)" = 0 ] || fail "Root permission is required."
  [ ! -L "$DATA" ] || fail "Refusing a symlink data directory."
  mkdir -p "$DATA/settings" "$DATA/providers" "$DATA/run" "$DATA/config" "$DATA/runtime" "$DATA/logs"
  chmod 700 "$DATA" "$DATA/settings" "$DATA/providers" "$DATA/run" "$DATA/config" "$DATA/runtime" "$DATA/logs"
}
init_settings() {
  for item in mode:test port:12346 api_port:9091 bootstrap:223.5.5.5:53 autostart:0; do
    key=${item%%:*}; default=${item#*:}
    [ ! -L "$DATA/settings/$key" ] || fail "Refusing a symlink setting."
    [ -f "$DATA/settings/$key" ] || put "$key" "$default"
  done
  if [ ! -f "$DATA/settings/api_secret" ]; then
    secret=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')
    [ "${#secret}" = 48 ] || fail "Cannot generate an API token."
    put api_secret "$secret"
  fi
}
lock() {
  exec 9>"$DATA/run/controller.lock"
  if [ "$command" = hot-install ]; then
    flock -w 10 9 || fail "Another operation is still in progress; hot activation did not run."
  else
    flock -n 9 || fail "Another operation is in progress."
  fi
}
valid_port() {
  case "$1" in ''|*[!0-9]*|??????*) return 1;; esac
  [ "$1" -ge 1024 ] && [ "$1" -le 65535 ]
}
valid_dns() {
  printf '%s\n' "$1" | awk -F '[.:]' '
    NF != 5 { exit 1 }
    { for (i=1;i<=5;i++) if ($i !~ /^[0-9]+$/) exit 1;
      for (i=1;i<=4;i++) if ($i+0>255) exit 1;
      if ($5+0<1 || $5+0>65535) exit 1; }'
}
ticks() {
  # The process name may contain spaces; starttime is field 20 after comm.
  line=$(cat "$PROC_ROOT/$1/stat" 2>/dev/null) || return 1
  rest=${line##*) }
  printf '%s\n' "$rest" | awk '$1 != "Z" && NF >= 20 {print $20}'
}
owned_pid() {
  [ -f "$DATA/run/core.pid" ] || return 1
  record=$(cat "$DATA/run/core.pid")
  pid=${record%%:*}; expected=${record#*:}
  case "$pid:$expected" in *[!0-9:]*|:*|*:) return 1;; esac
  [ "$pid" -gt 1 ] || return 1
  current=$(ticks "$pid") || return 1
  [ -n "$current" ] && [ "$current" = "$expected" ] || return 1
  executable=$(readlink "$PROC_ROOT/$pid/exe" 2>/dev/null) || return 1
  executable=${executable% (deleted)}
  if [ "$executable" != "$CORE" ]; then
    case "$executable" in
      "$HOT_TRASH_ROOT"/honksu.*/bin/honk-core)
        archived=${executable#"$HOT_TRASH_ROOT"/honksu.}
        archived=${archived%/bin/honk-core}
        case "$archived" in ''|*[!0-9]*) return 1;; esac;;
      *) return 1;;
    esac
  fi
  kill -0 "$pid" 2>/dev/null || return 1
  printf '%s\n' "$pid"
}
provider_count() {
  count=0
  for f in "$DATA/providers"/p*.url; do [ ! -f "$f" ] || count=$((count+1)); done
  printf '%s' "$count"
}
generate() {
  tmp="$DATA/config/.config.$$"
  {
    printf "global {\n tproxy_port: %s\n data_dir: '%s/runtime'\n bootstrap_resolver: '%s'\n nfqueue_enable: false\n preconnect_node_count: 0\n udp_warm_node_count: 0\n log_level: info\n check_interval: 300s\n}\n" "$(value port)" "$DATA" "$(value bootstrap)"
    printf 'subscription {\n'
    for f in "$DATA/providers"/p*.url; do
      [ -f "$f" ] || continue
      id=${f##*/}; id=${id%.url}
      url=$(cat "$f")
      printf " %s: '%s' {\n  route: direct\n  interval: 86400s\n }\n" "$id" "$url"
    done
    printf '}\n'
    if [ "$(provider_count)" -gt 0 ]; then
      printf 'group {\n PROXY {\n  policy: min_moving_avg\n }\n}\nrouting {\n fallback: PROXY\n}\n'
    else
      printf 'routing {\n fallback: block\n}\n'
    fi
    printf "experimental {\n clash_api {\n  external_controller: '127.0.0.1:%s'\n  secret: '%s'\n }\n}\n" "$(value api_port)" "$(value api_secret)"
  } > "$tmp"
  chmod 600 "$tmp"
  mv -f "$tmp" "$DATA/config/config.dae"
}
status() {
  running=0; pid=0
  if current=$(owned_pid); then running=1; pid=$current; fi
  printf 'running=%s\npid=%s\nmode=%s\nport=%s\napi_port=%s\nbootstrap=%s\nautostart=%s\nproviders=%s\nebpf_available=0\n' \
    "$running" "$pid" "$(value mode)" "$(value port)" "$(value api_port)" "$(value bootstrap)" "$(value autostart)" "$(provider_count)"
  if [ -x "$CORE" ]; then printf 'core_present=1\n'; else printf 'core_present=0\n'; fi
  current_core=0
  if [ "$running" = 1 ]; then
    image=$(readlink "$PROC_ROOT/$pid/exe" 2>/dev/null || true)
    [ "$image" != "$CORE" ] || current_core=1
  fi
  printf 'running_core_current=%s\nhot_install=%s\n' "$current_core" "$(cat "$DATA/run/hotinstall.status" 2>/dev/null || printf none)"
  dirty=0
  if [ "$running" = 1 ]; then
    active=$(cat "$DATA/run/config.hash" 2>/dev/null || true)
    pending=$(sha256sum "$DATA/config/config.dae" | awk '{print $1}')
    [ "$active" = "$pending" ] || dirty=1
  fi
  printf 'pending_restart=%s\n' "$dirty"
  if [ -f "$MODDIR/core.prop" ]; then cat "$MODDIR/core.prop"; fi
}
check_core() {
  [ -x "$CORE" ] || fail "Missing executable honk-core. Reinstall the built module ZIP."
  if [ "${CORE_CHECKED:-0}" != 1 ]; then
    timeout 3 "$CORE" --version >/dev/null 2>&1 || fail "The core cannot execute on this Android system."
    CORE_CHECKED=1
  fi
}
start() {
  [ "$(value mode)" = test ] || fail "Android eBPF interception is not ready; only test mode is supported."
  check_core
  if owned_pid >/dev/null; then printf 'Core process is already running.\n'; return; fi
  generate
  if [ -f "$DATA/logs/core.log" ] && [ "$(wc -c < "$DATA/logs/core.log")" -gt 2097152 ]; then
    mv -f "$DATA/logs/core.log" "$DATA/logs/core.previous.log"
  fi
  nohup env TOKIO_WORKER_THREADS=4 "$CORE" --mock-ebpf --config "$DATA/config/config.dae" --data-dir "$DATA/runtime" \
    >>"$DATA/logs/core.log" 2>&1 </dev/null 9>&- &
  pid=$!
  sleep 1
  stamp=$(ticks "$pid" 2>/dev/null || true)
  [ -n "$stamp" ] || fail "The core exited during startup. Open the log for details."
  printf '%s:%s\n' "$pid" "$stamp" > "$DATA/run/core.pid"
  owned_pid >/dev/null || fail "The core exited during startup. Open the log for details."
  sha256sum "$DATA/config/config.dae" | awk '{print $1}' > "$DATA/run/config.hash"
  printf 'Core test process started; traffic interception is disabled.\n'
}
stop() {
  if ! pid=$(owned_pid); then rm -f "$DATA/run/core.pid"; printf 'Core process is stopped.\n'; return; fi
  kill -TERM "$pid"
  n=0
  while owned_pid >/dev/null; do
    n=$((n+1))
    [ "$n" -le 10 ] || break
    sleep 1
  done
  if pid=$(owned_pid); then
    kill -KILL "$pid"
    sleep 1
    if owned_pid >/dev/null; then fail "The core has not exited yet."; fi
  fi
  rm -f "$DATA/run/core.pid" "$DATA/run/config.hash"
  printf 'Core process stopped.\n'
}
hot_install() {
  check_core
  resume_after_hot=0
  if owned_pid >/dev/null; then resume_after_hot=1; fi
  stop
  if [ "$resume_after_hot" = 1 ]; then start; fi
  printf 'complete\n' > "$DATA/run/hotinstall.status"
  trap - EXIT
  printf 'Hot installation complete. Previous running/stopped state and saved settings are preserved.\n'
}
add_provider() {
  [ "$#" = 2 ] || fail "A name and URL are required."
  [ "${#1}" -le 256 ] && [ "${#2}" -le 12000 ] || fail "Subscription input is too long."
  name=$(decode "$1") || fail "Invalid name encoding."
  url=$(decode "$2") || fail "Invalid URL encoding."
  [ "${#url}" -le 8192 ] || fail "The URL is too long."
  [ -n "$name" ] && [ "${#name}" -le 120 ] || fail "The name must contain 1–120 bytes."
  case "$url" in http://?*|https://?*) ;; *) fail "An HTTP(S) subscription URL is required.";; esac
  [ "$(printf '%s' "$url" | wc -l)" -eq 0 ] || fail "The URL must be a single line."
  # Restrict the dae-quoted URL to printable URI characters, including no quotes.
  printf '%s' "$url" | LC_ALL=C grep -Eq '^[][A-Za-z0-9._~:/?#@!$&()*+,;=%-]+$' || fail "Invalid URL characters."
  for f in "$DATA/providers"/p*.url; do
    [ -f "$f" ] || continue
    [ "$(cat "$f")" != "$url" ] || fail "This subscription is already saved."
  done
  [ "$(provider_count)" -lt 32 ] || fail "The first version supports at most 32 subscriptions."
  index=1
  while [ -e "$DATA/providers/p$index.url" ]; do index=$((index+1)); done
  printf '%s' "$name" | b64 > "$DATA/providers/p$index.name"
  printf '%s' "$url" > "$DATA/providers/p$index.url"
  generate
  printf 'Subscription saved; honk loads it at the next core start.\n'
}
list_providers() {
  for f in "$DATA/providers"/p*.url; do
    [ -f "$f" ] || continue
    id=${f##*/}; id=${id%.url}
    printf '%s\t%s\t' "$id" "$(cat "$DATA/providers/$id.name")"
    cat "$f" | b64
    printf '\n'
  done
}

command=${1:-status}
shift || true
init
if [ "$command" = hot-install ]; then
  printf 'pending\n' > "$DATA/run/hotinstall.status"
  trap '[ "$?" -eq 0 ] || printf "failed\n" > "$DATA/run/hotinstall.status"' EXIT
fi
lock
init_settings
case "$command" in
  status) [ "$#" = 0 ] || fail "Unexpected arguments."; status;;
  providers) list_providers;;
  add) add_provider "$@";;
  remove)
    [ "$#" = 1 ] || fail "A subscription ID is required."
    case "$1" in p[0-9]*) ;; *) fail "Invalid subscription ID.";; esac
    id=${1#p}; case "$id" in ''|*[!0-9]*) fail "Invalid subscription ID.";; esac
    rm -f "$DATA/providers/$1.url" "$DATA/providers/$1.name"
    generate; printf 'Subscription removed.\n';;
  settings)
    [ "$#" = 5 ] || fail "Five settings are required."
    [ "$1" = test ] || fail "eBPF inbound is not implemented yet."
    valid_port "$2" && valid_port "$3" && [ "$2" != "$3" ] || fail "Use two different ports from 1024 to 65535."
    valid_dns "$4" || fail "Use a numeric IPv4 DNS server with a port."
    case "$5" in 0|1) ;; *) fail "Invalid autostart value.";; esac
    put mode "$1"; put port "$2"; put api_port "$3"; put bootstrap "$4"; put autostart "$5"
    generate; printf 'Settings saved; restart a running core to apply them.\n';;
  start) start;;
  stop) stop;;
  restart) check_core; stop; start;;
  hot-install) [ "$#" = 0 ] || fail "Unexpected arguments."; hot_install;;
  boot) [ "$(value autostart)" != 1 ] || start;;
  logs)
    if [ -f "$DATA/logs/core.log" ]; then tail -n 180 "$DATA/logs/core.log" | sed -E 's#https?://[^[:space:]]+#[subscription URL]#g'; fi;;
  clear-log) : > "$DATA/logs/core.log"; printf 'Log cleared.\n';;
  *) fail "Unknown command.";;
esac
