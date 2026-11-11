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
    if(kind==='bank'){
      var bacct=document.getElementById('bacct'),bankVal=document.getElementById('bankValue'),bfield=document.getElementById('bankField'),
          blabel=document.getElementById('bankLabel'),bsheet=document.getElementById('bankSheet'),blist=document.getElementById('bankList'),
          bdet=document.getElementById('bankDetail'),bmsg=document.getElementById('bankMsg'),btimer,bseq=0,matches=[],curAcct='';
      var PH='Enter the account number first';
      function bmsgShow(t){bmsg.hidden=!t;bmsg.textContent=t||''}
      function closeBankSheet(){bsheet.hidden=true}
      function resetBank(){bankVal.value='';form.dataset.who='';to=null;matches=[];blist.innerHTML='';closeBankSheet();bdet.hidden=true;bmsgShow('');
        bfield.disabled=true;blabel.textContent=PH;blabel.className='ph';doQuote()}
      function openBankSheet(){
        blist.innerHTML='';
        matches.forEach(function(n){var li=document.createElement('li');if(n===bankVal.value)li.className='sel';
          var sp=document.createElement('span');sp.textContent=n;var r=document.createElement('i');r.className='radio';li.appendChild(sp);li.appendChild(r);
          li.addEventListener('click',function(){chooseBank(n)});blist.appendChild(li)});
        if(document.activeElement)document.activeElement.blur();bsheet.hidden=false}
      function chooseBank(name){
        closeBankSheet();blabel.textContent=name;blabel.className='';
        var my=++bseq;bdet.hidden=true;bankVal.value='';form.dataset.who='';
        fetch('/api/bank-lookup?acct='+curAcct+'&bank='+encodeURIComponent(name)).then(function(r){return r.json()}).then(function(j){
          if(my!==bseq)return;
          if(!j.found){bmsgShow('Service unavailable for this financial institution');return}
          bmsgShow('');bankVal.value=j.bank;to=j.currency;form.dataset.who=j.name+' ('+j.bank+')';
          document.getElementById('bdName').textContent=j.name;document.getElementById('bdBank').textContent=j.bank;
          document.getElementById('bdNum').textContent=j.number;document.getElementById('bdCur').textContent=j.currency;
          bdet.hidden=false;doQuote()}).catch(function(){bmsgShow('Could not look up the account. Try again.')})}
      bfield.addEventListener('click',function(){if(matches.length)openBankSheet()});
      bsheet.addEventListener('click',function(e){if(e.target.closest('[data-bank-close]'))closeBankSheet()});
      bacct.addEventListener('input',function(){
        var v=bacct.value.replace(/\D/g,'');resetBank();clearTimeout(btimer);bseq++;curAcct=v;
        if(v.length<6)return;
        var my=bseq;
        btimer=setTimeout(function(){
          fetch('/api/bank-lookup?acct='+v).then(function(r){return r.json().then(function(j){return[r.status,j]})}).then(function(x){
            if(my!==bseq)return;
            if(x[0]!==200){bmsgShow(x[1].error||'Try again shortly.');return}
            matches=x[1].banks||[];
            if(!matches.length){if(v.length>=10)bmsgShow('Service unavailable for this financial institution');return}
            bfield.disabled=false;blabel.textContent='Select bank';blabel.className='ph';openBankSheet()}).catch(function(){})},300)
      });
    }
  }
  // PIN bottom sheet: opens when Send is tapped, submits the form once 4 digits are entered
  var send=document.getElementById('sendBtn'),sheet=document.getElementById('pinSheet');
  if(send&&sheet&&form){
    var pinVal=document.getElementById('pinValue'),dots=sheet.querySelectorAll('#pinDots i'),
        perr=document.getElementById('pinErr'),sum=document.getElementById('pinSummary'),pin='',busy=false;
    function paint(){dots.forEach(function(d,i){d.classList.toggle('on',i<pin.length)})}
    function openPin(){
      if(!form.checkValidity()){form.reportValidity();return}
      if(form.dataset.kind==='bank'&&!document.getElementById('bankValue').value){var bm=document.getElementById('bankMsg');bm.hidden=false;bm.textContent='Enter the account number, then choose the bank.';return}
      var a=document.getElementById('amt'),q=document.getElementById('quote'),who=document.getElementById('lookup');
      sum.textContent=form.dataset.who?form.dataset.who+(a&&a.value?' · Amount '+a.value:'')+(q&&!q.hidden?' · '+q.textContent.split(' · ')[0]:''):(who&&!who.hidden&&who.textContent.indexOf('✓')===0?who.textContent.replace('✓ ','')+' · ':'')+
        (a&&a.value?'Amount '+a.value:'')+(q&&!q.hidden?' · '+q.textContent.split(' · ')[0]:'');
      pin='';busy=false;perr.hidden=true;paint();sheet.hidden=false;document.body.style.overflow='hidden';
    }
    function closePin(){sheet.hidden=true;document.body.style.overflow='';pin='';paint()}
    function press(k){
      if(busy)return;
      if(k==='del')pin=pin.slice(0,-1);
      else if(/^\d$/.test(k)&&pin.length<4)pin+=k;
      paint();
      if(pin.length===4){busy=true;pinVal.value=pin;setTimeout(function(){form.submit()},120)}
    }
    send.addEventListener('click',openPin);
    sheet.addEventListener('click',function(e){
      if(e.target.closest('[data-pin-close]')){closePin();return}
      var b=e.target.closest('[data-k]');if(b)press(b.dataset.k)});
    document.addEventListener('keydown',function(e){
      if(sheet.hidden)return;
      if(e.key==='Escape')closePin();else if(e.key==='Backspace')press('del');else if(/^\d$/.test(e.key))press(e.key)});
    form.addEventListener('submit',function(e){if(!/^\d{4}$/.test(pinVal.value)){e.preventDefault();openPin()}});
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
