//Conexão Banco
const supabaseUrl = 'https://nwzijdudhemuibsyzpub.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc';
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

// FUNÇÃO PARA MENSAGENS CUSTOMIZADAS
const mostrarAviso = (texto, tipo = "sucesso") => {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast-msg ${tipo === "erro" ? "erro" : ""}`;
    toast.innerText = texto;
    
    container.innerHTML = ""; // Limpa anterior
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 400);
    }, 3000);
};

// --- REGISTRO ---
document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('regEmail').value;
    const password = document.getElementById('regPassword').value;
    const nome = document.getElementById('regName').value;

    const { data, error } = await _supabase.auth.signUp({
        email, password,
        options: { data: { full_name: nome } }
    });

    if (error) {
        mostrarAviso("Erro no cadastro: " + error.message, "erro");
    } else {
        await _supabase.from('usuarios').insert([{ nome, email }]);
        mostrarAviso("Cadastro finalizado! Faça seu login.");
        
        // REDIRECIONA PARA O LOGIN (Troca a aba)
        setTimeout(() => { toggleView(); }, 2000); 
    }
});

// --- LOGIN ---
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;

    const { data, error } = await _supabase.auth.signInWithPassword({ email, password });

    if (error) {
        mostrarAviso("Email ou senha inválidos.", "erro");
    } else {

        const nomeUsuario = data.user.user_metadata.full_name; 
        localStorage.setItem('usuarioNome', nomeUsuario);     
        
        mostrarAviso(`Bem-vindo, ${nomeUsuario}!`);
        
        // REDIRECIONA PARA A TELA DE APRESENTAÇÃO
        setTimeout(() => {
            window.location.href = "../Tela-apresentação/index-apresentação.html";
        }, 1250);
    }
});




const signinForm = document.querySelector(".form.signin");
const signupForm = document.querySelector(".form.signup");
const cardBg1 = document.querySelector(".card-bg-1");
const cardBg2 = document.querySelector(".card-bg-2");

const toggleView = () => {
  const signinActive = signinForm.classList.contains("active");

  signinForm.classList.toggle("active", !signinActive);
  signupForm.classList.toggle("active", signinActive);

  [cardBg1, cardBg2].forEach((el) =>
    el.classList.toggle("signin", signinActive)
  );
  [cardBg1, cardBg2].forEach((el) =>
    el.classList.toggle("signup", !signinActive)
  );
};
