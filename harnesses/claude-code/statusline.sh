#!/usr/bin/env bash

input=$(cat)

model=$(printf '%s' "$input" | jq -r '.model.display_name // empty' | sed 's/^Claude //')
ctx=$(printf '%s' "$input" | jq -r 'if .context_window.used_percentage != null then (.context_window.used_percentage | floor | tostring) else "" end')
cwd=$(printf '%s' "$input" | jq -r '.workspace.current_dir // empty')
rl_5h=$(printf '%s' "$input" | jq -r 'if .rate_limits.five_hour.used_percentage != null then (.rate_limits.five_hour.used_percentage | floor | tostring) else "" end')
rl_7d=$(printf '%s' "$input" | jq -r 'if .rate_limits.seven_day.used_percentage != null then (.rate_limits.seven_day.used_percentage | floor | tostring) else "" end')

folder=""
branch=""
if [ -n "$cwd" ]; then
    folder="${cwd##*/}"
    branch=$(git --no-optional-locks -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
fi

parts=()
[ -n "$model" ]  && parts+=("$model")
[ -n "$ctx" ]    && parts+=("${ctx}% ctx")
[ -n "$folder" ] && parts+=("$folder")
[ -n "$branch" ] && parts+=("$branch")

rate_str=""
[ -n "$rl_5h" ] && rate_str="5h:${rl_5h}%"
if [ -n "$rl_7d" ]; then
    [ -n "$rate_str" ] && rate_str="${rate_str}  "
    rate_str="${rate_str}7d:${rl_7d}%"
fi
[ -n "$rate_str" ] && parts+=("$rate_str")

sep="  |  "
result=""
for part in "${parts[@]}"; do
    [ -z "$result" ] && result="$part" || result="${result}${sep}${part}"
done

printf '%s\n' "$result"
