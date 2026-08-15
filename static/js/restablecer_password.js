(() => {
  "use strict";
  document.addEventListener("DOMContentLoaded",()=>{
    document.querySelectorAll("[data-password-toggle]").forEach(button=>button.addEventListener("click",()=>{const input=document.getElementById(button.dataset.passwordToggle);if(!input)return;const show=input.type==="text";input.type=show?"password":"text";const icon=button.querySelector("i");icon.classList.toggle("fa-eye",show);icon.classList.toggle("fa-eye-slash",!show);}));
    const first=document.getElementById("id_new_password1"),second=document.getElementById("id_new_password2");if(!first||!second)return;
    const update=()=>{document.getElementById("reset-rule-length")?.classList.toggle("valid",first.value.length>=8);document.getElementById("reset-rule-nonnumeric")?.classList.toggle("valid",Boolean(first.value)&&!/^\d+$/.test(first.value));document.getElementById("reset-rule-match")?.classList.toggle("valid",Boolean(first.value)&&first.value===second.value);};
    [first,second].forEach(input=>input.addEventListener("input",update));update();
  });
})();
