import{Q as e,nt as t,ot as n}from"./keymap-D2-SJ0ji.js";import{t as r}from"./paths-BRSOhVgH.js";var i=e=>e.join(`
`);async function a(a,s=i){let c=a?a.getData(`text/plain`):await navigator.clipboard?.readText()??``;if(c&&s===i||a&&!o(a)||!t())return c;try{let t=await e(n.clipboardFileList());return c&&c.replace(/\r\n/g,`
`).split(`
`).map(r).join(`
`)!==t.join(`
`)?c:s(t)}catch{return c}}function o(e){return!!e.files.length||Array.from(e.types).includes(`Files`)}function s(e,t,n=i){let r=e.clipboardData;return e.defaultPrevented||!r||r.getData(`text/plain`)&&n===i||!o(r)?!1:(e.preventDefault(),e.stopImmediatePropagation(),a(r,n).then(e=>{e&&t(e)}),!0)}export{a as n,s as t};
//# sourceMappingURL=clipboard-BJ-ulOpI.js.map