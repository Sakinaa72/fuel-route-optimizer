window.addEventListener("load", () => {
  if (window.SwaggerUIBundle) {
    SwaggerUIBundle({url: "/openapi.json", dom_id: "#swagger-ui", validatorUrl: null,
      supportedSubmitMethods: ["get", "post"], displayRequestDuration: true});
  }
});
