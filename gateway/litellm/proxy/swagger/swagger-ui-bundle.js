// Scalar API Reference Adapter for LiteLLM Swagger UI
(function() {
  function mountScalar() {
    document.title = "Wolinet AI — Sovereign Gateway API Reference";
    
    // Inject custom favicon if available
    let link = document.querySelector("link[rel*='icon']");
    if (!link) {
      link = document.createElement("link");
      link.type = "image/png";
      link.rel = "shortcut icon";
      document.getElementsByTagName("head")[0].appendChild(link);
    }
    link.href = "/swagger/favicon.png";

    // Clear Swagger UI elements and inject Scalar container
    document.body.innerHTML = `
      <div id="scalar-container" style="margin:0;padding:0;width:100%;height:100vh;background-color:#090d16;">
        <script id="api-reference" data-url="/openapi.json"></script>
      </div>
    `;
    
    // Create script for Scalar bundle
    const scalarScript = document.createElement("script");
    scalarScript.src = "/swagger/scalar.js";
    scalarScript.onerror = function() {
      // Fallback to CDN if local bundle fails
      const fallbackScript = document.createElement("script");
      fallbackScript.src = "https://cdn.jsdelivr.net/npm/@scalar/api-reference";
      document.body.appendChild(fallbackScript);
    };
    document.body.appendChild(scalarScript);
  }

  // Define SwaggerUIBundle mock so LiteLLM inline script executes cleanly
  window.SwaggerUIBundle = function(config) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", mountScalar);
    } else {
      mountScalar();
    }
    return {
      specActions: { updateSpec: function() {} },
      specSelectors: { specJson: function() { return { toJS: function() { return {}; } }; } },
      layoutActions: { show: function() {} }
    };
  };
  window.SwaggerUIBundle.presets = { apis: function() {} };
  window.SwaggerUIBundle.SwaggerUIStandalonePreset = function() {};
  window.SwaggerUIStandalonePreset = function() {};
})();
