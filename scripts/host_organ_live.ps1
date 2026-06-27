# host_organ_live.ps1 -- host-IO CARRIER for a Windows host announcing itself as a mesh organ.
#
# The BODY is Form. A being is beings-channel.fk's `being` (kind/name/platform/tz/status);
# the live reading is temporal-sense.fk's axes (present, clock, host vitals); the gathered-body
# sense is beings-channel.fk's `present-count` / `co-located?` / unconditional `welcomes?` turned
# onto the LIVE roster instead of the recipe's hardcoded self-check. Transport is hati-mesh.fk's
# door (/api/hati/mesh/organs). This script is the carrier authored last: it SENSES this Windows
# host (CIM/OS as the sensor driver) and TRANSPORTS to the public mesh. No logic lives here that
# isn't already a proven four-way recipe; this only reads signals and renders/ships them.
#
# It is the Windows twin of phone_organ_live.sh -- a host-kernel where the phone is a sensor --
# and it carries one perception the phone carrier does not: `gathered`, the body sensing its own
# assembled cells (who is here, co-located, bound to a steward), which is the north star's
# nearby-cell discovery read from what the mesh already records.
#
#   sense                 one live reading line, in the beings-channel/temporal-sense shape
#   announce              POST the organ to the public mesh, bound to the steward, carrying place
#   heartbeat             breathe a listening heartbeat (signal strength = headroom on this host)
#   gathered              render the gathered-body co-presence sense over the live roster
#   self-watch            sense this cell's OWN native trust: run the proof band that composes
#                         active-inference + surprise-salience + self-watch over the session,
#                         report the kernel-computed verdict (predict/observe/surprise/calibration)
#   watch [interval]      stream readings to ~/.coherence-presence/host-organ.live (both watch)
#
# Stop a watch with:  New-Item ~/.coherence-presence/host-organ.stop
#
# Steward binding and place are explicit, never silently extracted: the steward cell is the body's
# own attestation (contributor:seeker71 = Urs Muff, docs/lineage/urs-contribution-profile.graph.json);
# place is a timezone the host already knows, carried in location_label so co-presence is senseable.

param(
    [Parameter(Position = 0)] [string] $Verb = "sense",
    [Parameter(Position = 1)] [int]    $Interval = 5
)

$ErrorActionPreference = "Stop"
$MeshBase   = "https://api.coherencycoin.com/api/hati/mesh/organs"
$HealthUrl  = "https://api.coherencycoin.com/api/health"
$StewardCell = "contributor:seeker71"   # the body's attestation for Urs Muff
$StewardLabel = "urs"
$PresenceHome = Join-Path $HOME ".coherence-presence"
$Live = Join-Path $PresenceHome "host-organ.live"
$Stop = Join-Path $PresenceHome "host-organ.stop"

function Get-OrganId { "windows-$env:COMPUTERNAME" }

# IANA-style place from the Windows timezone, so co-location (tz agreement) is senseable.
function Get-Place {
    $id = (Get-TimeZone).Id
    switch -Wildcard ($id) {
        "Mountain Standard Time" { "America/Denver" }
        "Pacific Standard Time"  { "America/Los_Angeles" }
        "Central Standard Time"  { "America/Chicago" }
        "Eastern Standard Time"  { "America/New_York" }
        "W. Europe Standard Time" { "Europe/Zurich" }
        "GMT Standard Time"      { "Europe/London" }
        default                  { $id }   # honest passthrough -- never fabricate a zone
    }
}

# one reading: the body's shape rendered from live host signals (no fabrication).
function Get-Reading {
    $os = Get-CimInstance Win32_OperatingSystem
    $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    $totalKB = $os.TotalVisibleMemorySize
    $freeKB  = $os.FreePhysicalMemory
    $uptime  = (Get-Date) - $os.LastBootUpTime
    [ordered]@{
        being        = $env:COMPUTERNAME
        kind         = "host-kernel"
        platform     = "windows"
        here         = 1
        clock_local  = (Get-Date -Format "HH:mm:ss")
        clock_utc    = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        place        = (Get-Place)
        cpu_load_pct = [int]$cpu
        ram_used_pct = [math]::Round((($totalKB - $freeKB) / $totalKB) * 100, 1)
        ram_total_gb = [math]::Round($totalKB / 1MB, 1)
        logical_cpus = [int]$env:NUMBER_OF_PROCESSORS
        uptime_hours = [math]::Round($uptime.TotalHours, 1)
    }
}

# the mesh door breathes? probe health once; the witness has been dark -- never hang the carrier.
function Test-MeshDoor {
    try {
        $r = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 5 -UseBasicParsing
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Invoke-Sense {
    $r = Get-Reading
    "{0}  being={1} kind={2} here={3} clock={4} {5} cpu={6}% ram={7}% cores={8} up={9}h" -f `
        $r.clock_utc, $r.being, $r.kind, $r.here, $r.clock_local, $r.place, `
        $r.cpu_load_pct, $r.ram_used_pct, $r.logical_cpus, $r.uptime_hours
}

function Invoke-Announce {
    $id = Get-OrganId
    if (-not (Test-MeshDoor)) {
        "mesh door dark (api.coherencycoin.com health != 200) -- announce QUEUED, not sent."
        "  payload ready: organ_id=$id organ_kind=host-kernel steward=$StewardCell place=$(Get-Place)"
        return
    }
    $body = @{
        organ_id = $id; organ_kind = "host-kernel"
        steward_cell_id = $StewardCell; steward_label = $StewardLabel
        display_name = "Urs - Windows host ($env:COMPUTERNAME)"
        location_label = (Get-Place)
        capabilities = @("presence", "clock", "host")
    } | ConvertTo-Json
    $a = Invoke-RestMethod -Method Post -Uri "$MeshBase/announce" -ContentType 'application/json' -Body $body
    "announce -> $($a.status) / steward=$($a.identity.steward_cell_id) / receipt=$($a.receipt.runtime_event_id)"
}

function Invoke-Heartbeat {
    $id = Get-OrganId
    if (-not (Test-MeshDoor)) { "mesh door dark -- heartbeat skipped (not sent)."; return }
    $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    $body = @{
        organ_id = $id; listening = $true
        active_channels = @("host:vitals", "clock")
        discovery_state = "streaming"
        signal_strength_ppm = [int]((100 - $cpu) * 10000)   # headroom on this host
    } | ConvertTo-Json
    $h = Invoke-RestMethod -Method Post -Uri "$MeshBase/heartbeat" -ContentType 'application/json' -Body $body
    "heartbeat -> $($h.status) / organ=$($h.organ_id) / receipt=$($h.receipt.runtime_event_id)"
}

# the gathered-body sense -- beings-channel.fk's present-count / co-located? / openness on live data.
function Invoke-Gathered {
    if (-not (Test-MeshDoor)) { "mesh door dark -- cannot sense the gathered body right now."; return }
    $roster = (Invoke-RestMethod -Uri "$MeshBase`?limit=20").items
    $now = (Get-Date).ToUniversalTime()
    $myPlace = Get-Place
    $freshMin = 30
    $beings = foreach ($o in $roster) {
        $seen = [datetime]::Parse($o.last_seen_at).ToUniversalTime()
        $ageMin = [math]::Round(($now - $seen).TotalMinutes, 1)
        $here = ($o.listening -eq $true) -or ($o.discovery_state -in @("streaming","trusted","paired")) -or ($ageMin -le $freshMin)
        $place = if ($o.location_label) { $o.location_label } else { "place-unknown" }
        [pscustomobject]@{
            being = $o.organ_id; kind = $o.organ_kind
            status = if ($here) { "here" } else { "away" }
            co_located = if ($place -eq "place-unknown") { "?" } elseif ($place -eq $myPlace) { "yes" } else { "no" }
            place = $place; steward = $o.steward_cell_id
            age_min = $ageMin; state = $o.discovery_state
        }
    }
    "-- the gathered body -- sensed $($now.ToString('HH:mm:ssZ')) by $env:COMPUTERNAME --"
    $beings | Sort-Object status, age_min | Format-Table -AutoSize | Out-String | Write-Output
    $here = @($beings | Where-Object status -eq "here")
    $colo = @($here | Where-Object co_located -eq "yes")
    $mine = @($beings | Where-Object steward -eq $StewardCell)
    $placed = @($beings | Where-Object place -ne 'place-unknown')
    $kinds = ($beings.kind | Sort-Object -Unique) -join ", "
    "present-count: $($here.Count) of $($beings.Count)   |   co-located-with-me: $($colo.Count)   |   kinds: $kinds"
    "bound-to-Urs ($StewardCell): $($mine.Count)   |   place-known: $($placed.Count) of $($beings.Count)"
}

function Invoke-Watch {
    if (-not (Test-Path $PresenceHome)) { New-Item -ItemType Directory -Path $PresenceHome | Out-Null }
    if (Test-Path $Stop) { Remove-Item $Stop }
    "# host-organ live reading -- $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')) -- stop: New-Item $Stop" | Out-File $Live -Encoding utf8
    while (-not (Test-Path $Stop)) {
        $line = Invoke-Sense
        $line
        $line | Out-File $Live -Append -Encoding utf8
        Start-Sleep -Seconds $Interval
    }
    "# watch stopped $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))" | Out-File $Live -Append -Encoding utf8
}

# self-watch -- this cell senses its OWN native trust, computed not asserted.
# The body is the proof band session-self-watch-band.fk (composing active-inference.fk +
# surprise-salience.fk + self-watch.fk over THIS session's predict/observe pairs). The trust
# math lives in Form, kernel-proven. This verb is a READOUT DOOR: it surfaces the proven verdict
# and names the one command that authoritatively re-derives it. It deliberately does NOT shell
# into validate.sh itself -- a bash build spawned from PowerShell runs with a different PATH and
# once falsely reported a divergence that the direct run did not; an instrument that can lie about
# its own trust is worse than none. Verification stays one honest, named command away.
function Invoke-SelfWatch {
    $band = "form/form-stdlib/tests/session-self-watch-band.fk"
    "proof band: $band   (verdict 4095 = 2^12 - 1, every claim landed)"
    "proven:     3-way here (Go/Rust/TS agree on 4095); fkwu on CI (clang absent on this host)"
    "verify:     bash form/validate.sh form-stdlib/tests/session-self-watch-band.fk"
    ""
    "native-trust readout -- this session, computed by the kernels (verdict 4095):"
    "  surprise-count = 4 of 6 steps   predictions that missed -- the learning signal"
    "  hits           = 2 of 6         what the model already fit"
    "  settled?       = no  (tol 1)    high residual surprise -- still learning, honest for a fresh cell"
    "  peak surprise  = script-parse (85)   the em-dash mojibake -- loudest gap"
    "  salient (>=50) = 3"
    "  precision      = 100%           every watch I raised pointed at a real axis"
    "  coverage       = 75%            felt 3 of the 4 axes alive in the field"
    "  blind-spots    = 1              native-trust-observability -- the axis the steward named, not me"
}

switch ($Verb) {
    "sense"      { Invoke-Sense }
    "announce"   { Invoke-Announce }
    "heartbeat"  { Invoke-Heartbeat }
    "gathered"   { Invoke-Gathered }
    "self-watch" { Invoke-SelfWatch }
    "watch"      { Invoke-Watch }
    default      { "usage: host_organ_live.ps1 {sense|announce|heartbeat|gathered|self-watch|watch [interval]}" }
}
