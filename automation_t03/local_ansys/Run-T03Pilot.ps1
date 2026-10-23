[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Job,
    [string]$Python = 'python',
    [string]$Workbench = 'C:\Program Files\ANSYS Inc\v252\Framework\bin\Win64\RunWB2.exe',
    [int]$Processors = 4,
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Runner = Join-Path $PSScriptRoot 'run_design.py'
$Inputs = Join-Path $PSScriptRoot 'T03_inputs.json'
$Template = Join-Path $Repo 'automation_t03\reference_inputs\team_additions\baseline_fair_600Pa_result.cas.h5'
function Invoke-Stage([string[]]$Arguments) {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Stage failed (exit $LASTEXITCODE). Inspect job logs; no DOE result should be consumed." }
}
Invoke-Stage -Arguments @($Runner,'prepare','--inputs',$Inputs,'--job',$Job,'--template',$Template)
if ($Execute) {
    if (-not (Test-Path $Workbench -PathType Leaf)) { throw "Workbench executable not found: $Workbench" }
    Invoke-Stage -Arguments @($Runner,'mesh','--job',$Job,'--workbench',$Workbench)
    Invoke-Stage -Arguments @($Runner,'solve','--job',$Job,'--pressures','2500','--processors',"$Processors")
    Invoke-Stage -Arguments @($Runner,'validate-pilot','--job',$Job)
    Write-Output "Local pilot validation completed. Evidence: $Job\pilot_validation.json"
} else {
    Write-Output "Prepared CAD and batch files only. ANSYS was not executed. Use a NEW Job with -Execute to run the pilot."
}
