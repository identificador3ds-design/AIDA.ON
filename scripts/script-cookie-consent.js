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
        bottom: 18px;
        width: min(760px, calc(100% - 28px));
        height: auto;
        min-height: 0;
        margin: 0;
        box-sizing: border-box;
        transform: translateX(-50%);
        z-index: 3000;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 16px;
        align-items: center;
        padding: 16px;
        border: 1px solid rgba(229, 231, 235, 0.18);
        border-radius: 18px;
        background: rgba(8, 29, 28, 0.96);
        color: #f4f8ff;
        box-shadow: 0 18px 44px rgba(4, 8, 20, 0.36);
        backdrop-filter: blur(12px);
      }

      .cookie-consent p {
        margin: 0;
        color: rgba(229, 231, 235, 0.82);
        line-height: 1.5;
        font-size: 0.95rem;
      }

      .cookie-consent strong {
        display: block;
        margin-bottom: 4px;
        color: #ffffff;
        font-size: 1rem;
      }

      .cookie-consent a {
        color: #8fd8b7;
        font-weight: 700;
        text-decoration: underline;
        text-underline-offset: 3px;
      }

      .cookie-consent-actions {
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .cookie-consent button {
        min-height: 42px;
        padding: 0 16px;
        border: 1px solid rgba(229, 231, 235, 0.18);
        border-radius: 999px;
        cursor: pointer;
        color: #0f3833;
        background: linear-gradient(135deg, #e5e7eb, #97bfaf);
        font: inherit;
        font-weight: 700;
      }

      .cookie-consent button.secondary {
        color: #f4f8ff;
        background: rgba(229, 231, 235, 0.08);
      }

      @media (max-width: 660px) {
        .cookie-consent {
          grid-template-columns: 1fr;
        }

        .cookie-consent-actions,
        .cookie-consent button {
          width: 100%;
        }

        .cookie-consent-actions {
          flex-direction: column-reverse;
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
        <strong>Cookies e preferencias</strong>
        <p>
          Usamos cookies essenciais e armazenamento local para login, preferencias e funcionamento do AIDA.ON.
          Veja detalhes no <a href="${location.pathname.includes("/pages/") ? "./index-privacidade.html" : "pages/index-privacidade.html"}">Aviso de Privacidade</a>.
        </p>
      </div>
      <div class="cookie-consent-actions">
        <button type="button" class="secondary" data-cookie-choice="essential">Apenas essenciais</button>
        <button type="button" data-cookie-choice="accepted">Aceitar cookies</button>
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
