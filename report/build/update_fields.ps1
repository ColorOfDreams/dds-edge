param(
  [string]$In  = "D:\work\bigdata_btl\drivefocus\report\build\stage1.docx",
  [string]$Out = "D:\work\bigdata_btl\drivefocus\report\DriveFocus_BaoCao_ThiGiacMayTinh.docx",
  [string]$Pdf = "D:\work\bigdata_btl\drivefocus\report\build\report_preview.pdf"
)
$ErrorActionPreference = "Stop"
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
try {
  $d = $w.Documents.Open($In, $false, $false)
  $d.Repaginate()
  $d.Fields.Update() | Out-Null
  foreach ($i in 1..$d.TablesOfContents.Count) { $d.TablesOfContents.Item($i).Update() }
  foreach ($i in 1..$d.TablesOfFigures.Count) { $d.TablesOfFigures.Item($i).Update() }
  $d.Repaginate()
  foreach ($i in 1..$d.TablesOfContents.Count) { $d.TablesOfContents.Item($i).UpdatePageNumbers() }
  foreach ($i in 1..$d.TablesOfFigures.Count) { $d.TablesOfFigures.Item($i).UpdatePageNumbers() }
  $d.SaveAs2($Out, 16)
  $d.ExportAsFixedFormat($Pdf, 17)
  "pages: " + $d.ComputeStatistics(2)
  "tocs: " + $d.TablesOfContents.Count + " tofs: " + $d.TablesOfFigures.Count
  $d.Close($false)
} finally {
  $w.Quit()
}
