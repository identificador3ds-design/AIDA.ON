(function () {
  const COOKIE_NAME = "aida_cookie_consent";
  const STORAGE_KEY = "AIDA_COOKIE_CONSENT";
  const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

  function getCookie(name) {
    return document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith(`${name}=`))
      ?.split("=")[1] || "";
  }

  function salvarConsentimento(valor) {
    const encoded = encodeURIComponent(valor);
    document.cookie = `${COOKIE_NAME}=${encoded}; Max-Age=${ONE_YEAR_SECONDS}; Path=/; SameSite=Lax`;
    localStorage.setItem(STORAGE_KEY, valor);
  }

  function consentimentoExistente() {
    return localStorage.getItem(STORAGE_KEY) || decodeURIComponent(getCookie(COOKIE_NAME));
  }

  function inserirEstilos() {
    if (document.getElementById("aidaCookieConsentStyles")) {
      return;
    }

    const style = document.createElement("style");
    style.id = "aidaCookieConsentStyles";
    style.textContent = `
      .cookie-consent {
        position: fixed;
        left: 50%;
        bottom: 24px;
        width: min(600px, calc(100% - 32px));
        height: auto;
        box-sizing: border-box;
        transform: translateX(-50%);
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 0;
        background: rgba(7, 21, 19, 0.95);
        color: #e2e8f0;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
        border-left: 3px solid #4ade80;
        backdrop-filter: blur(8px);
        font-family: "Afacad", Arial, sans-serif;
      }

      .cookie-consent p {
        margin: 0;
        color: #94a3b8;
        line-height: 1.5;
        font-size: 0.9rem;
      }

      .cookie-consent strong {
        display: block;
        margin-bottom: 6px;
        color: #ffffff;
        font-size: 1rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
      }

      .cookie-consent a {
        color: #4ade80;
        font-weight: 600;
        text-decoration: none;
        border-bottom: 1px solid rgba(74, 222, 128, 0.3);
      }
      
      .cookie-consent a:hover {
        border-bottom-color: #4ade80;
      }

      .cookie-consent-actions {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 12px;
        margin-top: 4px;
      }

      .cookie-consent button {
        height: 38px;
        padding: 0 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 0;
        cursor: pointer;
        color: #000000;
        background: #4ade80;
        font-family: inherit;
        font-weight: 700;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        transition: all 0.2s;
      }

      .cookie-consent button:hover {
        background: #22c55e;
      }

      .cookie-consent button.secondary {
        color: #e2e8f0;
        background: transparent;
      }

      .cookie-consent button.secondary:hover {
        border-color: rgba(255, 255, 255, 0.3);
        background: rgba(255, 255, 255, 0.05);
      }

      @media (max-width: 500px) {
        .cookie-consent-actions {
          flex-direction: column-reverse;
          width: 100%;
        }
        .cookie-consent button {
          width: 100%;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function fecharBanner(banner) {
    banner.remove();
  }

  function criarBanner() {
    if (consentimentoExistente()) {
      return;
    }

    inserirEstilos();

    const banner = document.createElement("section");
    banner.className = "cookie-consent";
    banner.setAttribute("aria-label", "Aviso de cookies");
    banner.innerHTML = `
      <div>
        <strong>AVISO DE COOKIES</strong>
        <p>
          Utilizamos armazenamento local para manter sua sessão e funcionamento do AIDA.ON. 
          Detalhes no <a href="${location.pathname.includes("/pages/") ? "./index-privacidade.html" : "pages/index-privacidade.html"}">Aviso de Privacidade</a>.
        </p>
      </div>
      <div class="cookie-consent-actions">
        <button type="button" class="secondary" data-cookie-choice="essential">Apenas essenciais</button>
        <button type="button" data-cookie-choice="accepted">Aceitar todos</button>
      </div>
    `;

    banner.addEventListener("click", (event) => {
      const button = event.target.closest("[data-cookie-choice]");

      if (!button) {
        return;
      }

      salvarConsentimento(button.dataset.cookieChoice);
      fecharBanner(banner);
    });

    document.body.appendChild(banner);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", criarBanner);
  } else {
    criarBanner();
  }
})();
