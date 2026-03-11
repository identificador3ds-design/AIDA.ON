const supabaseUrl = 'https://nwzijdudhemuibsyzpub.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc';
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

function base64ToBlob(base64, mime) {
    const byteString = atob(base64.split(',')[1]);
    const bytes = new Uint8Array(byteString.length);

    for (let i = 0; i < byteString.length; i++) {
        bytes[i] = byteString.charCodeAt(i);
    }

    return new Blob([bytes], { type: mime });
}

function obterMimeType(base64) {
    const correspondencia = base64.match(/^data:(.*?);base64,/);
    return correspondencia ? correspondencia[1] : 'image/png';
}

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

function montarDescricaoMetodo(dados) {
    const metodoRetornado = (dados.metodo || '').toLowerCase();

    if (metodoRetornado.includes('marca visual')) {
        const iaNome = dados.metodo.replace('Marca Visual (', '').replace(')', '');
        return `DETECCAO POR MARCA VISUAL\n\nFoi identificada uma marca d'agua visual no canto inferior direito da imagem, caracteristica da ferramenta ${iaNome}. Esta e uma assinatura visual explicita inserida por geradores de imagem.`;
    }

    if (metodoRetornado.includes('metadados')) {
        const iaNome = dados.metodo.replace('Metadados (', '').replace(')', '');
        return `DETECCAO POR METADADOS\n\nOs metadados da imagem contem assinaturas digitais caracteristicas da ferramenta ${iaNome}.`;
    }

    if (metodoRetornado.includes('lsb')) {
        return `ANALISE LSB (PLANO DE BITS)\n\nO plano de bits menos significativos apresenta ${dados.energia} pixels ativos. Uma alta concentracao de bits alterados pode indicar a presenca de marcas d'agua digitais ou esteganografia.`;
    }

    if (
        metodoRetornado.includes('gradiente') ||
        metodoRetornado.includes('laplaciano') ||
        metodoRetornado.includes('neon')
    ) {
        return `ANALISE DE GRADIENTE LAPLACIANO (EFEITO NEON)\n\nO filtro Laplaciano detectou bordas com intensidade media de ${dados.energia}. O efeito neon realca as regioes de maior variacao na imagem, que podem corresponder a texturas sinteticas ou artefatos caracteristicos de imagens geradas por IA.`;
    }

    if (
        metodoRetornado.includes('frequencia') ||
        metodoRetornado.includes('fft') ||
        metodoRetornado.includes('consistencia')
    ) {
        return `ANALISE DE FREQUENCIA (FFT)\n\nA analise tecnica de frequencias detectou uma energia de ${dados.energia}. Valores fora da faixa tipica podem indicar manipulacao sintetica.`;
    }

    return `RESULTADO DA ANALISE\n\nMetodo utilizado: ${dados.metodo}\nProbabilidade: ${dados.probabilidade}\nEnergia detectada: ${dados.energia}`;
}

document.addEventListener('DOMContentLoaded', () => {
    const nomeSalvo = localStorage.getItem('usuarioNome');
    const botaoUsuario = document.getElementById('nome-usuario2');
    const btnSair = document.getElementById('btn-sair');

    if (nomeSalvo && botaoUsuario) {
        botaoUsuario.innerText = `Ola, ${nomeSalvo}`;
        gsap.from('#nome-usuario2', { opacity: 0, duration: 1, y: -10 });
    }

    if (btnSair) {
        btnSair.addEventListener('click', (e) => {
            e.preventDefault();
            localStorage.removeItem('usuarioNome');
            window.location.href = '../login/index-login.html';
        });
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const imagemPreview = document.getElementById('imagemPreview');
    const placeholderImagem = document.getElementById('placeholderImagem');
    const btnVerificar = document.getElementById('btnVerificar');
    const btnTrocar = document.getElementById('btnTrocar');
    const inputTrocarImagem = document.getElementById('inputTrocarImagem');
    const tipoImagemInput = document.getElementById('tipoImagem');
    const metodoAnalise = document.getElementById('metodoAnalise');
    const checkMarcaDagua = document.getElementById('checkMarcaDagua');
    const checkMetadados = document.getElementById('checkMetadados');
    const loading = document.getElementById('loading');
    const areaResultado = document.getElementById('areaResultado');
    const imagemProcessada = document.getElementById('imagemProcessada');
    const porcentagemIA = document.getElementById('porcentagemIA');
    const tituloMetodo = document.getElementById('tituloMetodo');
    const textoMetodo = document.getElementById('textoMetodo');

    let imagemAtual = localStorage.getItem('AIDA_ImagemSelecionada') || '';

    function limparResultado() {
        if (loading) {
            loading.style.display = 'none';
        }

        if (areaResultado) {
            areaResultado.style.display = 'none';
        }

        if (imagemProcessada) {
            imagemProcessada.src = '#';
        }

        if (porcentagemIA) {
            porcentagemIA.innerText = '0%';
        }

        if (tituloMetodo) {
            tituloMetodo.innerText = 'Sobre o Metodo';
        }

        if (textoMetodo) {
            textoMetodo.innerText = 'Aguardando processamento...';
        }
    }

    function atualizarPreviewImagem(imagemBase64) {
        if (!imagemPreview || !placeholderImagem) {
            return;
        }

        if (imagemBase64) {
            imagemPreview.src = imagemBase64;
            imagemPreview.hidden = false;
            placeholderImagem.hidden = true;
            return;
        }

        imagemPreview.src = '#';
        imagemPreview.hidden = true;
        placeholderImagem.hidden = false;
    }

    function definirImagemAtual(imagemBase64) {
        imagemAtual = imagemBase64 || '';

        if (imagemAtual) {
            localStorage.setItem('AIDA_ImagemSelecionada', imagemAtual);
        } else {
            localStorage.removeItem('AIDA_ImagemSelecionada');
        }

        atualizarPreviewImagem(imagemAtual);
        limparResultado();
    }

    atualizarPreviewImagem(imagemAtual);
    limparResultado();

    if (btnTrocar && inputTrocarImagem) {
        btnTrocar.addEventListener('click', () => {
            inputTrocarImagem.value = '';
            inputTrocarImagem.click();
        });

        inputTrocarImagem.addEventListener('change', () => {
            const arquivo = inputTrocarImagem.files[0];

            if (!arquivo) {
                return;
            }

            const reader = new FileReader();
            reader.onload = (evento) => {
                definirImagemAtual(evento.target.result);

                if (tipoImagemInput) {
                    tipoImagemInput.value = '';
                }

                mostrarAlerta('Imagem trocada. Escolha o metodo e analise novamente.');
            };
            reader.readAsDataURL(arquivo);
        });
    }

    if (metodoAnalise) {
        metodoAnalise.addEventListener('change', () => {
            limparResultado();
        });
    }

    if (checkMarcaDagua) {
        checkMarcaDagua.addEventListener('change', () => {
            limparResultado();
        });
    }

    if (checkMetadados) {
        checkMetadados.addEventListener('change', () => {
            limparResultado();
        });
    }

    if (btnVerificar) {
        btnVerificar.addEventListener('click', async () => {
            const metodoSelecionado = metodoAnalise ? metodoAnalise.value : '';
            const analisarMarcaDagua = checkMarcaDagua ? checkMarcaDagua.checked : true;
            const analisarMetadados = checkMetadados ? checkMetadados.checked : true;

            if (!imagemAtual) {
                mostrarAlerta('Selecione uma imagem antes de analisar.');
                return;
            }

            if (!metodoSelecionado) {
                mostrarAlerta('Selecione o metodo de analise.');
                return;
            }

            limparResultado();

            if (loading) {
                loading.style.display = 'block';
            }

            try {
                const response = await fetch('https://aida-on.onrender.com/analisar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        imagem: imagemAtual,
                        metodo: metodoSelecionado,
                        analisarMarcaDagua,
                        analisarMetadados
                    })
                });

                const dados = await response.json();

                if (!response.ok || dados.status !== 'sucesso') {
                    throw new Error(dados.mensagem || 'Falha ao analisar a imagem.');
                }

                if (loading) {
                    loading.style.display = 'none';
                }

                if (areaResultado) {
                    areaResultado.style.display = 'block';
                }

                if (imagemProcessada) {
                    imagemProcessada.src = dados.imagem_fft || '#';
                }

                if (porcentagemIA) {
                    porcentagemIA.innerText = dados.probabilidade || '0%';
                }

                if (tituloMetodo) {
                    tituloMetodo.innerText = dados.metodo || 'Sobre o Metodo';
                }

                if (textoMetodo) {
                    textoMetodo.innerText = montarDescricaoMetodo(dados);
                }

                mostrarAlerta('Analise concluida!');

                const { data: { user } } = await _supabase.auth.getUser();

                if (!user) {
                    console.warn('Nenhum usuario logado. O historico nao sera salvo.');
                    return;
                }

                const mimeType = obterMimeType(imagemAtual);
                const subtipo = mimeType.split('/')[1] || 'png';
                const extensao = subtipo === 'jpeg' ? 'jpg' : subtipo;
                const blob = base64ToBlob(imagemAtual, mimeType);
                const nomeArquivo = `${user.id}/${Date.now()}_original.${extensao}`;

                const { error: uploadError } = await _supabase.storage
                    .from('evidencias')
                    .upload(nomeArquivo, blob);

                if (uploadError) {
                    console.error('Erro no upload do storage:', uploadError.message);
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
                    console.error('Erro ao salvar na tabela:', dbError.message);
                    return;
                }

                console.log('Analise salva com sucesso no banco de dados.');
            } catch (erro) {
                if (loading) {
                    loading.style.display = 'none';
                }

                console.error('Erro ao processar imagem:', erro);
                mostrarAlerta('Erro ao processar imagem.');
            }
        });
    }
});
