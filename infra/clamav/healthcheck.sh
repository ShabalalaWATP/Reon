#!/bin/sh

set -eu

maximum_hours="${CLAMAV_SIGNATURE_MAX_AGE_HOURS:-48}"
check_daemon="${CLAMAV_HEALTH_CHECK_DAEMON:-true}"
requested_now_epoch="${1:-}"
case "$maximum_hours" in
    ''|*[!0-9]*)
        echo "ERROR: CLAMAV_SIGNATURE_MAX_AGE_HOURS must be an integer" >&2
        exit 1
        ;;
esac
if [ "$maximum_hours" -lt 1 ] || [ "$maximum_hours" -gt 168 ]; then
    echo "ERROR: signature maximum age must be between 1 and 168 hours" >&2
    exit 1
fi
case "$check_daemon" in
    true|false) ;;
    *)
        echo "ERROR: CLAMAV_HEALTH_CHECK_DAEMON must be true or false" >&2
        exit 1
        ;;
esac

latest_signature=""
latest_info=""
disk_version=0
for signature in /var/lib/clamav/daily.cvd /var/lib/clamav/daily.cld; do
    if [ -f "$signature" ]; then
        info="$(sigtool --info "$signature")" || {
            echo "ERROR: ClamAV signature metadata is invalid" >&2
            exit 1
        }
        version="$(
            printf '%s\n' "$info" |
                awk -F ': ' '$1 == "Version" { print $2; exit }'
        )"
        case "$version" in
            ''|*[!0-9]*)
                echo "ERROR: ClamAV signature version is invalid" >&2
                exit 1
                ;;
        esac
        if [ "$version" -gt "$disk_version" ]; then
            disk_version="$version"
            latest_signature="$signature"
            latest_info="$info"
        fi
    fi
done
if [ -z "$latest_signature" ]; then
    echo "ERROR: no daily ClamAV signature database is available" >&2
    exit 1
fi

build_time="$(
    printf '%s\n' "$latest_info" |
        awk -F ': ' '$1 == "Build time" { print $2; exit }'
)"
set -- $build_time
if [ "$#" -ne 5 ]; then
    echo "ERROR: ClamAV signature build time is invalid" >&2
    exit 1
fi
build_day="$1"
build_month="$2"
build_year="$3"
build_clock="$4"
build_zone="$5"
case "$build_month" in
    Jan) build_month_number=01 ;;
    Feb) build_month_number=02 ;;
    Mar) build_month_number=03 ;;
    Apr) build_month_number=04 ;;
    May) build_month_number=05 ;;
    Jun) build_month_number=06 ;;
    Jul) build_month_number=07 ;;
    Aug) build_month_number=08 ;;
    Sep) build_month_number=09 ;;
    Oct) build_month_number=10 ;;
    Nov) build_month_number=11 ;;
    Dec) build_month_number=12 ;;
    *)
        echo "ERROR: ClamAV signature build month is invalid" >&2
        exit 1
        ;;
esac
case "$build_clock" in
    *:*:*) ;;
    *:*) build_clock="${build_clock}:00" ;;
    *)
        echo "ERROR: ClamAV signature build clock is invalid" >&2
        exit 1
        ;;
esac
case "$build_zone" in
    [+-][0-9][0-9][0-9][0-9]) ;;
    *)
        echo "ERROR: ClamAV signature build zone is invalid" >&2
        exit 1
        ;;
esac
build_epoch="$(
    date -u -d \
        "${build_year}-${build_month_number}-${build_day} ${build_clock} ${build_zone}" \
        +%s
)" || {
    echo "ERROR: ClamAV signature build time cannot be parsed" >&2
    exit 1
}

now_epoch="${requested_now_epoch:-$(date -u +%s)}"
case "$now_epoch" in
    ''|*[!0-9]*)
        echo "ERROR: health-check time must be an epoch integer" >&2
        exit 1
        ;;
esac
age_seconds=$(( now_epoch - build_epoch ))
maximum_seconds=$(( maximum_hours * 3600 ))
if [ "$age_seconds" -lt 0 ] || [ "$age_seconds" -gt "$maximum_seconds" ]; then
    echo "ERROR: ClamAV signatures exceed the permitted age" >&2
    exit 1
fi

if [ "$check_daemon" = "true" ]; then
    /usr/local/bin/clamdcheck.sh >/dev/null
    loaded_version="$(clamdscan --version | cut -d/ -f2)"
    if [ "$loaded_version" != "$disk_version" ]; then
        clamdscan --reload >/dev/null 2>&1 || true
        echo "ERROR: clamd has not loaded the current signature database" >&2
        exit 1
    fi
fi

echo "ClamAV signature freshness and configured daemon checks are healthy"
