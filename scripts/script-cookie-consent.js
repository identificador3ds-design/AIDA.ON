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
        padding: 24px;
        border: 1px solid rgba(229, 231, 235, 0.12);
        border-radius: 24px;
        background: rgba(12, 49, 46, 0.95);
        color: #f4f8ff;
        box-shadow: 0 16px 38px rgba(4, 8, 20, 0.28);
        backdrop-filter: blur(12px);
        font-family: "Afacad", Arial, sans-serif;
      }

      .cookie-consent p {
        margin: 0;
        color: rgba(209, 213, 219, 0.82);
        line-height: 1.58;
        font-size: 1.05rem;
      }

      .cookie-consent strong {
        display: block;
        margin-bottom: 8px;
        color: #8fd8b7;
        font-size: 1.1rem;
        text-transform: uppercase;
        letter-spacing: 0.18em;
      }

      .cookie-consent a {
        color: #8fd8b7;
        font-weight: 600;
        text-decoration: none;
        border-bottom: 1px solid rgba(143, 216, 183, 0.3);
        transition: border-bottom-color 0.2s;
      }
      
      .cookie-consent a:hover {
        border-bottom-color: #8fd8b7;
      }

      .cookie-consent-actions {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 12px;
        margin-top: 8px;
      }

      .cookie-consent button {
        min-height: 44px;
        padding: 0 24px;
        border-radius: 999px;
        border: 1px solid rgba(229, 231, 235, 0.16);
        cursor: pointer;
        color: #0f3833;
        background: linear-gradient(135deg, #e5e7eb 0%, #ced9d6 48%, #9fc3b5 100%);
        font-family: inherit;
        font-weight: 700;
        font-size: 0.95rem;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
      }

      .cookie-consent button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(12, 49, 46, 0.2);
      }

      .cookie-consent button.secondary {
        color: #e5e7eb;
        background: linear-gradient(180deg, rgba(229, 231, 235, 0.1), rgba(209, 213, 219, 0.04));
        border-color: rgba(229, 231, 235, 0.14);
        box-shadow: none;
      }

      .cookie-consent button.secondary:hover {
        background: linear-gradient(180deg, rgba(229, 231, 235, 0.15), rgba(209, 213, 219, 0.08));
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
