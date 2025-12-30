from pathlib import Path
p=Path('static/app.js')
text=p.read_text(encoding='utf-8', errors='ignore')
start=text.find('function copyWeekToNext(weekStart){')
end=text.find('function copyWeekFromPrevious', start)
if start==-1 or end==-1:
    raise SystemExit('not found')
replacement = """function copyWeekToNext(weekStart){
  if(!confirm(\"Bu haftadaki tum projeler sonraki haftaya kopyalansin mi? (Ustune yazar)\")) return;

  fetch(\"/api/copy_week_to_next\", {
    method:\"POST\",
    headers:{ \"Content-Type\":\"application/json\" },
    body: JSON.stringify({ week_start: weekStart })
  })
  .then(r=>r.json())
  .then(resp=>{
    if(!resp.ok){
      if(resp.blocked){
        alert(\"Bu personeller uygun degil:\\n\" + resp.blocked.map(b=>-  ()).join(\"\\n\"));
      } else {
        alert(resp.error || \"Kaydetme hatasi\");
      }
      return;
    }
    toast(\"Kopyalandi\");
    location.reload();
  })
  .catch(e=> alert(\"Kopyalama hatasi: \" + e));
}

function copyWeekFromPrevious"""
text = text[:start] + replacement + text[end:]
p.write_text(text, encoding='utf-8')
