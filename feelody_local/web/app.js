const $ = id => document.getElementById(id);
const diary=$('diary'), button=$('submit'), result=$('result');
diary.addEventListener('input',()=>{$('count').textContent=diary.value.length.toLocaleString('ko-KR')+' / 4,000';result.hidden=true;$('status').textContent='';});
$('form').addEventListener('submit',async e=>{
  e.preventDefault(); if(button.disabled) return;
  if(!diary.value.trim()){ $('status').textContent='먼저 일기를 적어줘.';diary.focus();return; }
  button.disabled=true;diary.readOnly=true;result.hidden=true;$('status').textContent='오늘의 곡을 찾고 있어…';
  try{
    const response=await fetch('/api/recommend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({diary:diary.value})});
    const data=await response.json();if(!response.ok) throw new Error(data.error||'추천에 실패했어.');
    const box=$('tracks');box.replaceChildren();
    for(const song of data.songs){
      const card=document.createElement('article'),title=document.createElement('h2'),artist=document.createElement('p'),link=document.createElement('a');
      title.textContent=song.title;artist.textContent=song.artist;
      link.href='https://www.melon.com/song/detail.htm?songId='+encodeURIComponent(song.song_id);
      link.target='_blank';link.rel='noreferrer';link.textContent='멜론에서 보기 ↗';card.append(title,artist,link);box.append(card);
    }
    result.hidden=false;$('status').textContent=data.songs.length>1?'같은 점수를 받은 곡들이야.':'한 곡을 골랐어.';
    result.scrollIntoView({block:'nearest'});
  }catch(err){$('status').textContent=err instanceof TypeError?'연결이 끊겼어. 실행 창을 확인하고 다시 시도해 줘.':err.message;}
  finally{button.disabled=false;diary.readOnly=false;}
});
