(() => {
  "use strict";
  const RUT=/^\d{7,8}-[\dkK]$/, PHONE=/^\+?\d{9,15}$/;
  const readJson=async(r)=>{try{return await r.json();}catch{return {};}};
  const firstError=(v)=>Array.isArray(v)?v.map(firstError).filter(Boolean).join(" "):v&&typeof v==="object"?Object.values(v).map(firstError).filter(Boolean).join(" "):typeof v==="string"?v:"";
  document.addEventListener("DOMContentLoaded",()=>{
    const root=document.getElementById("registro-cuenta"), form=document.getElementById("registro-form"); if(!root||!form)return;
    const names=["rut","username","first_name","last_name","telefono","email","password","password2"], fields=Object.fromEntries(names.map(n=>[n,form.elements[n]]));
    const errorBox=document.getElementById("register-error"), submit=document.getElementById("register-submit");
    const setError=(n,m)=>{const e=form.querySelector(`[data-error-for="${n}"]`);if(e)e.textContent=m||"";fields[n]?.classList.toggle("is-invalid",Boolean(m));};
    const showError=(m)=>{errorBox.textContent=m;errorBox.hidden=!m;};
    const updateRules=()=>{const p=fields.password.value,c=fields.password2.value;document.getElementById("rule-length").classList.toggle("valid",p.length>=8);document.getElementById("rule-nonnumeric").classList.toggle("valid",Boolean(p)&&!/^\d+$/.test(p));document.getElementById("rule-match").classList.toggle("valid",Boolean(p)&&p===c);};
    fields.rut.addEventListener("input",()=>fields.rut.value=fields.rut.value.replace(/[.\s]/g,"").toUpperCase());
    fields.telefono.addEventListener("input",()=>{const plus=fields.telefono.value.trim().startsWith("+");fields.telefono.value=`${plus?"+":""}${fields.telefono.value.replace(/\D/g,"")}`;});
    fields.email.addEventListener("blur",()=>fields.email.value=fields.email.value.trim().toLowerCase());
    fields.username.addEventListener("input",()=>fields.username.value=fields.username.value.replace(/\s/g,""));
    [fields.password,fields.password2].forEach(f=>f.addEventListener("input",updateRules));
    form.querySelectorAll("[data-password-toggle]").forEach(b=>b.addEventListener("click",()=>{const i=document.getElementById(b.dataset.passwordToggle),show=i.type==="text";i.type=show?"password":"text";const icon=b.querySelector("i");icon.classList.toggle("fa-eye",show);icon.classList.toggle("fa-eye-slash",!show);}));
    Object.entries(fields).forEach(([n,f])=>f.addEventListener("input",()=>{setError(n,"");showError("");}));
    const validate=()=>{names.forEach(n=>setError(n,""));const e={};if(!fields.first_name.value.trim())e.first_name="Ingresa tus nombres.";if(!fields.last_name.value.trim())e.last_name="Ingresa tus apellidos.";if(!RUT.test(fields.rut.value.trim()))e.rut="Usa el formato 12345678-9.";if(!PHONE.test(fields.telefono.value.trim()))e.telefono="Ingresa entre 9 y 15 dígitos.";if(fields.username.value.trim().length<3)e.username="El usuario debe tener al menos 3 caracteres.";if(!fields.email.validity.valid||!fields.email.value.trim())e.email="Ingresa un correo válido.";if(fields.password.value.length<8)e.password="Usa al menos 8 caracteres.";else if(/^\d+$/.test(fields.password.value))e.password="La contraseña no puede ser solo numérica.";if(fields.password.value!==fields.password2.value)e.password2="Las contraseñas no coinciden.";Object.entries(e).forEach(([n,m])=>setError(n,m));form.querySelector(".is-invalid")?.focus();return !Object.keys(e).length;};
    form.addEventListener("submit",async ev=>{ev.preventDefault();showError("");if(!validate()){showError("Revisa los campos marcados para continuar.");return;}const data=Object.fromEntries(new FormData(form).entries());delete data.csrfmiddlewaretoken;data.email=data.email.trim().toLowerCase();data.rut=data.rut.trim().toUpperCase();data.username=data.username.trim();submit.disabled=true;submit.querySelector("span").textContent="Creando cuenta…";try{const response=await fetch(root.dataset.registerUrl,{method:"POST",headers:{Accept:"application/json","Content-Type":"application/json","X-CSRFToken":form.elements.csrfmiddlewaretoken.value},body:JSON.stringify(data)}),result=await readJson(response);if(!response.ok){Object.entries(result).forEach(([n,v])=>fields[n]&&setError(n,firstError(v)));throw new Error(firstError(result)||"No fue posible completar el registro.");}window.location.assign(result.redirect_url||root.dataset.pendingUrl);}catch(error){showError(error.message||"No fue posible completar el registro.");submit.disabled=false;submit.querySelector("span").textContent="Crear cuenta y verificar correo";}});
  });
})();
