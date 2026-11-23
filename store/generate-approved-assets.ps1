#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$OutputDirectory
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path

function New-Brush([string]$ColorHtml) {
    return New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml($ColorHtml))
}

function Draw-Document {
    param(
        [System.Drawing.Graphics]$Graphics,
        [single]$X, [single]$Y, [single]$Width, [single]$Height
    )
    $White = New-Brush "#F8FCFF"
    $Grid = New-Brush "#8FD3F4"
    $Outline = New-Object System.Drawing.Pen ([System.Drawing.ColorTranslator]::FromHtml("#DCEEFF")), ([Math]::Max(1.0, $Width * 0.025))
    try {
        $Graphics.FillRectangle($White, $X, $Y, $Width, $Height)
        $Graphics.DrawRectangle($Outline, $X, $Y, $Width, $Height)
        $Fold = [single]($Width * 0.22)
        $Graphics.FillRectangle($Grid, $X + $Width - $Fold, $Y, $Fold, $Fold)

        $Pad = [single]($Width * 0.12)
        $CellW = [single]($Width * 0.17)
        $CellH = [single]($Height * 0.12)
        $GapX = [single]($Width * 0.055)
        $GapY = [single]($Height * 0.055)
        for ($Row = 0; $Row -lt 3; $Row++) {
            for ($Col = 0; $Col -lt 3; $Col++) {
                $CX = $X + $Pad + $Col * ($CellW + $GapX)
                $CY = $Y + $Height * 0.30 + $Row * ($CellH + $GapY)
                $Graphics.FillRectangle($Grid, $CX, $CY, $CellW, $CellH)
            }
        }
    }
    finally {
        $White.Dispose()
        $Grid.Dispose()
        $Outline.Dispose()
    }
}

function Draw-AuditorIcon {
    param(
        [System.Drawing.Graphics]$Graphics,
        [single]$X, [single]$Y, [single]$Size
    )
    Draw-Document -Graphics $Graphics -X ($X + $Size*0.04) -Y ($Y + $Size*0.04) -Width ($Size*0.50) -Height ($Size*0.66)
    Draw-Document -Graphics $Graphics -X ($X + $Size*0.25) -Y ($Y + $Size*0.16) -Width ($Size*0.50) -Height ($Size*0.66)

    $Navy = [System.Drawing.ColorTranslator]::FromHtml("#08458B")
    $Green = [System.Drawing.ColorTranslator]::FromHtml("#0DB15B")
    $White = [System.Drawing.ColorTranslator]::FromHtml("#FFFFFF")
    $CirclePen = New-Object System.Drawing.Pen $Navy, ([Math]::Max(2.0, $Size*0.045))
    $HandlePen = New-Object System.Drawing.Pen $Navy, ([Math]::Max(2.0, $Size*0.055))
    $CheckPen = New-Object System.Drawing.Pen $Green, ([Math]::Max(2.0, $Size*0.055))
    $CircleBrush = New-Object System.Drawing.SolidBrush $White
    try {
        $R = [single]($Size*0.19)
        $CX = [single]($X + $Size*0.61)
        $CY = [single]($Y + $Size*0.62)
        $Graphics.FillEllipse($CircleBrush, $CX-$R, $CY-$R, 2*$R, 2*$R)
        $Graphics.DrawEllipse($CirclePen, $CX-$R, $CY-$R, 2*$R, 2*$R)
        $Graphics.DrawLine($HandlePen, $CX+$R*0.72, $CY+$R*0.72, $X+$Size*0.86, $Y+$Size*0.88)
        $Graphics.DrawLine($CheckPen, $CX-$R*0.50, $CY, $CX-$R*0.10, $CY+$R*0.36)
        $Graphics.DrawLine($CheckPen, $CX-$R*0.10, $CY+$R*0.36, $CX+$R*0.55, $CY-$R*0.42)
    }
    finally {
        $CirclePen.Dispose()
        $HandlePen.Dispose()
        $CheckPen.Dispose()
        $CircleBrush.Dispose()
    }
}

function New-Asset {
    param(
        [string]$Name,
        [int]$Width,
        [int]$Height,
        [switch]$Wide
    )
    $Bitmap = New-Object System.Drawing.Bitmap $Width, $Height
    $Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
    $Graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $Graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

    $Rect = New-Object System.Drawing.Rectangle 0, 0, $Width, $Height
    $Start = [System.Drawing.ColorTranslator]::FromHtml("#1179E6")
    $End = [System.Drawing.ColorTranslator]::FromHtml("#064B9D")
    $Gradient = New-Object System.Drawing.Drawing2D.LinearGradientBrush $Rect, $Start, $End, 90.0
    try {
        $Graphics.FillRectangle($Gradient, $Rect)
        if ($Wide) {
            Draw-AuditorIcon -Graphics $Graphics -X 12 -Y 18 -Size 112
            $Divider = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(210,255,255,255)), 2
            $Font1 = New-Object System.Drawing.Font "Segoe UI", 21, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
            $Font2 = New-Object System.Drawing.Font "Segoe UI", 23, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
            $TextBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
            try {
                $Graphics.DrawLine($Divider, 126, 25, 126, 125)
                $Graphics.DrawString("Data Contract", $Font1, $TextBrush, 140, 34)
                $Graphics.DrawString("Auditor", $Font2, $TextBrush, 140, 73)
            }
            finally {
                $Divider.Dispose()
                $Font1.Dispose()
                $Font2.Dispose()
                $TextBrush.Dispose()
            }
        }
        else {
            $Margin = [single]([Math]::Max(3, $Width * 0.08))
            Draw-AuditorIcon -Graphics $Graphics -X $Margin -Y $Margin -Size ([single]($Width - 2*$Margin))
        }
        $Path = Join-Path $OutputDirectory $Name
        $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $Gradient.Dispose()
        $Graphics.Dispose()
        $Bitmap.Dispose()
    }
}

New-Asset -Name "StoreLogo.png" -Width 50 -Height 50
New-Asset -Name "Square44x44Logo.png" -Width 44 -Height 44
New-Asset -Name "Square150x150Logo.png" -Width 150 -Height 150
New-Asset -Name "Wide310x150Logo.png" -Width 310 -Height 150 -Wide

$Expected = @{
    "StoreLogo.png" = @(50,50)
    "Square44x44Logo.png" = @(44,44)
    "Square150x150Logo.png" = @(150,150)
    "Wide310x150Logo.png" = @(310,150)
}
foreach ($Name in $Expected.Keys) {
    $Path = Join-Path $OutputDirectory $Name
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Generated artwork missing: $Name" }
    $Image = [System.Drawing.Image]::FromFile($Path)
    try {
        if ($Image.Width -ne $Expected[$Name][0] -or $Image.Height -ne $Expected[$Name][1]) {
            throw "Generated artwork dimension mismatch: $Name"
        }
    }
    finally {
        $Image.Dispose()
    }
}
Write-Output "ARTWORK_GENERATED=$OutputDirectory"
Write-Output "ARTWORK_STATUS=OWNER_APPROVED_GENERATOR"
