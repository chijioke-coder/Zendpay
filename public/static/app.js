(function(){
  var root=document.documentElement;
  function applyTheme(t){try{localStorage.setItem('zp-theme',t)}catch(e){}
    var d=t==='dark'||(t==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);root.dataset.theme=d?'dark':'light';markThemes();}
  function markThemes(){var cur='system';try{cur=localStorage.getItem('zp-theme')||'system'}catch(e){}
    document.querySelectorAll('[data-set-theme]').forEach(function(b){b.classList.toggle('on',b.dataset.setTheme===cur)})}
  document.addEventListener('click',function(e){
    var t=e.target.closest('[data-theme-toggle]');if(t){applyTheme(root.dataset.theme==='dark'?'light':'dark');return}
    t=e.target.closest('[data-set-theme]');if(t){applyTheme(t.dataset.setTheme);return}
    t=e.target.closest('[data-eye]');if(t){var i=t.parentElement.querySelector('input');i.type=i.type==='password'?'text':'password';return}
    t=e.target.closest('[data-copy]');if(t){navigator.clipboard&&navigator.clipboard.writeText(t.dataset.copy);t.textContent='✓';setTimeout(function(){t.textContent='⧉'},1200);return}
    t=e.target.closest('[data-hide]');if(t){toggleHide();return}
  });
  markThemes();
  // hide/show balance (remembered)
  function paintHide(){var h=false;try{h=localStorage.getItem('zp-hide')==='1'}catch(e){}
    document.querySelectorAll('[data-secret]').forEach(function(el){el.textContent=h?'••••••':el.dataset.secret})}
  function toggleHide(){var h=false;try{h=localStorage.getItem('zp-hide')==='1';localStorage.setItem('zp-hide',h?'0':'1')}catch(e){}paintHide()}
  paintHide();
  // transfer helpers: recipient lookup + fee quote
  var csrf=(document.querySelector('meta[name=csrf]')||{}).content;
  var form=document.getElementById('tfForm');
  if(form){
    var kind=form.dataset.kind,acct=document.getElementById('acct'),amt=document.getElementById('amt'),
        look=document.getElementById('lookup'),quote=document.getElementById('quote'),to=null,timer;
    function doQuote(){if(!amt)return;clearTimeout(timer);timer=setTimeout(function(){
      if(!amt.value){quote.hidden=true;return}
      fetch('/api/quote?kind='+kind+'&amount='+encodeURIComponent(amt.value)+(to?'&to='+to:'')).then(function(r){return r.json()}).then(function(j){
        if(!j.ok){quote.hidden=true;return}quote.hidden=false;
        quote.textContent='Fee '+j.fee+' · You pay '+j.total+(j.converted?' · Recipient gets '+j.receives:'')}).catch(function(){})},250)}
    if(amt)amt.addEventListener('input',doQuote);
    if(acct)acct.addEventListener('input',function(){
      var v=acct.value.replace(/\D/g,'');to=null;look.hidden=true;
      if(v.length===10)fetch('/api/lookup?acct='+v).then(function(r){return r.json()}).then(function(j){
        look.hidden=false;if(j.found){to=j.currency;look.className='lookup';look.textContent='✓ '+j.name+' ('+j.currency+')';doQuote()}
        else{look.className='lookup bad';look.textContent='Account not found on Zendpay'}})});
  }
  // time zone: show times where the person is accessing from. Tell the server via a cookie.
  try{
    var tz=Intl.DateTimeFormat().resolvedOptions().timeZone,used=document.body.dataset.tz||'';
    if(tz&&tz!==used){
      document.cookie='zp_tz='+encodeURIComponent(tz)+'; path=/; max-age=31536000; SameSite=Lax'+(location.protocol==='https:'?'; Secure':'');
      if(document.querySelector('time.lt')&&!sessionStorage.getItem('zp-tz-reload')){sessionStorage.setItem('zp-tz-reload','1');location.reload();}
    }else{sessionStorage.removeItem('zp-tz-reload');}
  }catch(e){}
  // keep csrf header available for fetch posts
  window.ZP_CSRF=csrf;
})();
