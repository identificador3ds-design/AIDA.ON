const supabaseUrl = 'https://nwzijdudhemuibsyzpub.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc';
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

function base64ToBlob(base64, mime) {
    const byteString = atob(base64.split(',')[1]);
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i);
    }
    return new Blob([ab], { type: mime });
}
document.addEventListener('DOMContentLoaded', () => {
    // 1. Tenta recuperar o nome que o login guardou
    const nomeSalvo = localStorage.getItem('usuarioNome');
    const botaoUsuario = document.getElementById('nome-usuario2');

    console.log("Nome recuperado do localStorage:", nomeSalvo); // Para teste no F12

    if (nomeSalvo && botaoUsuario) {
        // 2. Muda o texto do botão
        botaoUsuario.innerText = `Olá, ${nomeSalvo}`;
        gsap.from("#nome-usuario2", { opacity: 0, duration: 1, y: -10 });
    } 

    // 3. Lógica do botão Sair (Logout)
    const btnSair = document.getElementById('btn-sair');
    if (btnSair) {
        btnSair.addEventListener('click', (e) => {
            e.preventDefault();
            localStorage.removeItem('usuarioNome');
            window.location.href = "../login/index-login.html";
        });
    }
});

function mostrarAlerta(mensagem) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast-card';
    toast.innerText = mensagem;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('fadeOut');
        setTimeout(() => toast.remove(), 500);
    }, 4000);
}

document.addEventListener('DOMContentLoaded', () => {
    const imagemPreview = document.getElementById('imagemPreview');
    const placeholderImagem = document.getElementById('placeholderImagem');
    const btnVerificar = document.getElementById('btnVerificar');

    const imagemSalva = localStorage.getItem('AIDA_ImagemSelecionada');

    if (!imagemSalva) {
        window.location.href = "../Ferramenta/index-seleciona.html";
        return;
    }

    if (imagemPreview) {
        imagemPreview.src = imagemSalva;
        imagemPreview.hidden = false;
        if (placeholderImagem) placeholderImagem.hidden = true;
    }

    if (btnVerificar) {
        btnVerificar.addEventListener('click', async () => {
            const metodoSelecionado = document.getElementById('metodoAnalise').value;
            const imagemBase64 = localStorage.getItem('AIDA_ImagemSelecionada');
            const loading = document.getElementById('loading');
            const areaResultado = document.getElementById('areaResultado');

            // DEBUG - verificar o valor do método
            console.log("Método selecionado:", metodoSelecionado);

            if (!metodoSelecionado || !imagemBase64) {
                mostrarAlerta("Selecione o método e uma imagem!");
                return;
            }

            areaResultado.style.display = 'none';
            loading.style.display = 'block';

            try {
                const response = await fetch('https://aida-on.onrender.com/analisar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ imagem: imagemBase64, metodo: metodoSelecionado })
                });

                const dados = await response.json();

                if (dados.status === "sucesso") {
                    loading.style.display = 'none';
                    areaResultado.style.display = 'block';

                    document.getElementById('imagemProcessada').src = dados.imagem_fft;
                    document.getElementById('porcentagemIA').innerText = dados.probabilidade;
                    document.getElementById('tituloMetodo').innerText = dados.metodo;

                    const textoElement = document.getElementById('textoMetodo');
                    const metodoRetornado = dados.metodo.toLowerCase();

                    console.log("Método retornado do backend:", dados.metodo); // DEBUG

                    if (metodoRetornado.includes("marca visual")) {
                        const iaNome = dados.metodo.replace("Marca Visual (", "").replace(")", "");
                        textoElement.innerText = `🔍 DETECÇÃO POR MARCA VISUAL\n\nFoi identificada uma marca d'água visual no canto inferior direito da imagem, característica da ferramenta ${iaNome}. Esta é uma assinatura visual explícita inserida por geradores de imagem.`;
                    } 
                    else if (metodoRetornado.includes("metadados")) {
                        const iaNome = dados.metodo.replace("Metadados (", "").replace(")", "");
                        textoElement.innerText = `🔍 DETECÇÃO POR METADADOS\n\nOs metadados da imagem contêm assinaturas digitais características da ferramenta ${iaNome}.`;
                    }
                    else if (metodoRetornado.includes("lsb")) {
                        textoElement.innerText = `🔍 ANÁLISE LSB (PLANO DE BITS)\n\nO plano de bits menos significativos apresenta ${dados.energia} pixels ativos. Uma alta concentração de bits alterados pode indicar a presença de marcas d'água digitais ou esteganografia.`;
                    }
                    else if (metodoRetornado.includes("frequência") || metodoRetornado.includes("fft") || metodoRetornado.includes("consistência")) {
                        textoElement.innerText = `🔍 ANÁLISE DE FREQUÊNCIA (FFT)\n\nA análise técnica de frequências detectou uma energia de ${dados.energia}. Valores fora da faixa típica podem indicar manipulação sintética.`;
                    }
                    else {
                        textoElement.innerText = `🔍 RESULTADO DA ANÁLISE\n\nMétodo utilizado: ${dados.metodo}\nProbabilidade: ${dados.probabilidade}\nEnergia detectada: ${dados.energia}`;
                    }

                    mostrarAlerta("Análise concluída!");

                    const { data: { user } } = await _supabase.auth.getUser();

                    if (user) {
                        console.log("Usuário logado detectado, iniciando salvamento...");
                        
                        const blob = base64ToBlob(imagemBase64, 'image/png');
                        const nomeArquivo = `${user.id}/${Date.now()}_original.png`;

                        const { data: uploadData, error: uploadError } = await _supabase.storage
                            .from('evidencias')
                            .upload(nomeArquivo, blob);

                        if (uploadError) {
                            console.error("Erro no Upload Storage:", uploadError.message);
                            return;
                        }

                        const { data: { publicUrl } } = _supabase.storage
                            .from('evidencias')
                            .getPublicUrl(nomeArquivo);

                        const { error: dbError } = await _supabase
                            .from('historico_analises')
                            .insert([{
                                user_id: user.id,
                                metodo: dados.metodo,
                                probabilidade: dados.probabilidade,
                                imagem_original: publicUrl,
                                resultado_img: dados.imagem_fft
                            }]);

                        if (dbError) {
                            console.error("Erro ao salvar na tabela:", dbError.message);
                        } else {
                            console.log("Salvo com sucesso no banco de dados!");
                        
                            localStorage.removeItem('AIDA_ImagemSelecionada');
                        }

                    } else {
                        console.warn("Nenhum usuário logado. O histórico não será salvo.");
                    }
                }
            } catch (erro) {
                if (loading) loading.style.display = 'none';
                mostrarAlerta("Erro ao processar imagem.");
            }
        });
    }

});

