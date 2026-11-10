(function(){
  var C=window.ZP_COUNTRIES,CUR=window.ZP_CURRENCIES,form=document.getElementById('signupForm'),step=1,
      country=null,currency=null,errBox=document.getElementById('formErr');
  var sheet=document.getElementById('sheet'),list=document.getElementById('sheetList'),search=document.getElementById('sheetSearch'),mode=null;
  function el(n){return form.elements[n]}
  function setStep(n){step=n;
    form.querySelectorAll('[data-step]').forEach(function(s){s.hidden=+s.dataset.step!==n});
    document.getElementById('stepSub').textContent='Step '+n+' of 3 — '+['Personal','Account','Security'][n-1]+' details';
    var sts=document.querySelectorAll('#stepper .st'),bars=document.querySelectorAll('#stepper .bar');
    sts.forEach(function(s,i){s.classList.toggle('done',i+1<n);s.classList.toggle('now',i+1===n);
      s.querySelector('i').textContent=i+1<n?'✓':['👤','⚙','🛡'][i]});
    bars.forEach(function(b,i){b.classList.toggle('done',i+1<n)});
    showErr('');window.scrollTo(0,0)}
  function showErr(m,field){errBox.hidden=!m;errBox.textContent=m||'';
    form.querySelectorAll('.invalid').forEach(function(x){x.classList.remove('invalid')});
    if(field){var f=el(field);var box=f?f.closest('.field'):form.querySelector('[data-pick='+field+']');if(box)box.classList.add('invalid')}}
  function validate(n){
    if(n===1){
      if(!el('surname').value.trim()||!el('first_name').value.trim())return['Enter your surname and first name.'];
      if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(el('email').value.trim()))return['Enter a valid email address.','email'];
      if(!country)return['Choose your country of residence.','country'];
      var p=el('phone').value.replace(/\D/g,'');if(p.length<6||p.length>14)return['Enter a valid phone number.','phone']}
    if(n===2&&!currency)return['Choose a primary currency.','currency'];
    if(n===3){var pw=el('password').value;
      if(pw.length<8||!/[A-Za-z]/.test(pw)||!/\d/.test(pw))return['Password must be at least 8 characters with letters and numbers.','password'];
      if(pw!==el('confirm').value)return['Passwords do not match.','confirm'];
      if(!/^\d{4}$/.test(el('pin').value))return['Transaction PIN must be exactly 4 digits.','pin'];
      if(!el('terms').checked)return['Please accept the Terms of Service and Privacy Policy.']}
    return null}
  form.addEventListener('click',function(e){
    if(e.target.closest('[data-next]')){var v=validate(step);if(v){showErr(v[0],v[1]);return}setStep(step+1)}
    if(e.target.closest('[data-back]'))setStep(step-1);
    var p=e.target.closest('[data-pick]');if(p)openSheet(p.dataset.pick)});
  el('pin').addEventListener('input',function(){this.value=this.value.replace(/\D/g,'').slice(0,4);
    document.querySelectorAll('#pinbar i').forEach(function(b,i){b.classList.toggle('on',i<el('pin').value.length)})});
  function items(){var q=search.value.trim().toLowerCase();
    if(mode==='country')return C.filter(function(c){return c.name.toLowerCase().indexOf(q)>-1}).map(function(c){return{key:c.name,label:c.name,sub:c.dial!=='0'?'+'+c.dial:'',sel:country&&country.name===c.name}});
    return Object.keys(CUR).filter(function(k){return(k+' '+CUR[k][0]).toLowerCase().indexOf(q)>-1}).map(function(k){return{key:k,label:CUR[k][0]+' ('+CUR[k][1]+')',sub:k,sel:currency===k}})}
  function render(){list.innerHTML='';items().forEach(function(it){var li=document.createElement('li');if(it.sel)li.className='sel';
    var s=document.createElement('span');s.textContent=it.label;var sm=document.createElement('small');sm.textContent=it.sub;s.appendChild(sm);
    var r=document.createElement('i');r.className='radio';li.appendChild(s);li.appendChild(r);
    li.addEventListener('click',function(){pick(it.key)});list.appendChild(li)})}
  function openSheet(m){mode=m;search.value='';render();sheet.hidden=false;setTimeout(function(){var s=list.querySelector('.sel');if(s)s.scrollIntoView({block:'center'})},0)}
  function pick(k){
    if(mode==='country'){country=C.find(function(c){return c.name===k});
      document.getElementById('countryLabel').textContent=country.name;
      document.getElementById('dialBox').textContent=country.dial!=='0'?'+'+country.dial:'—';
      if(!currency)setCurrency(country.currency,true)}
    else setCurrency(k);
    sheet.hidden=true;showErr('')}
  function setCurrency(k,soft){currency=k;var c=CUR[k];
    document.getElementById('currencyLabel').textContent=c[0]+' ('+c[1]+')';
    document.getElementById('curCard').hidden=false;document.getElementById('curSym').textContent=c[1];
    document.getElementById('curCode').textContent=k;document.getElementById('curName').textContent=c[0]}
  search.addEventListener('input',render);
  sheet.addEventListener('click',function(e){if(e.target.closest('[data-close]'))sheet.hidden=true});
  form.addEventListener('submit',function(e){e.preventDefault();var v=validate(3);if(v){showErr(v[0],v[1]);return}
    var btn=document.getElementById('createBtn');btn.disabled=true;
    var body={surname:el('surname').value,first_name:el('first_name').value,email:el('email').value,country:country.name,
      phone:el('phone').value,account_type:el('account_type').value,currency:currency,password:el('password').value,
      confirm:el('confirm').value,pin:el('pin').value,terms:el('terms').checked};
    fetch('/signup',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF':window.ZP_CSRF},body:JSON.stringify(body)})
      .then(function(r){return r.json().then(function(j){return[r.ok,j]})}).then(function(x){
        if(x[0]&&x[1].ok){location.href=x[1].next;return}
        btn.disabled=false;setStep(x[1].step||1);showErr(x[1].error||'Something went wrong.',x[1].field)})
      .catch(function(){btn.disabled=false;showErr('Network error. Try again.')})});
  setStep(1);
})();
