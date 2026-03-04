const supabaseUrl = 'https://nwzijdudhemuibsyzpub.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc';
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

document.addEventListener('DOMContentLoaded', async () => {
    const lista = document.getElementById('listaHistorico');
    const modal = document.getElementById('modalDetalhes');
    const btnLimpar = document.getElementById('btnLimparHistorico');

    // Variável global para o modal conseguir acessar depois
    let historicoNuvem = [];

    const carregarHistorico = async () => {
        lista.innerHTML = '<div class="spinner"></div><p style="text-align:center; width:100%; color:#c5dddb;">Buscando evidências na nuvem...</p>';

        //Verificar quem está logado
        const { data: { user } } = await _supabase.auth.getUser();

        if (!user) {
            lista.innerHTML = '<div class="mensagem-vazia">Você precisa estar logado para ver o histórico.</div>';
            return;
        }

        const { data: registros, error } = await _supabase
            .from('historico_analises')
            .select('*')
            .eq('user_id', user.id)
            .order('data_analise', { ascending: false });

        if (error) {
            console.error("Erro ao buscar dados:", error);
            lista.innerHTML = '<div class="mensagem-vazia" style="color:#ff4b4b;">Erro ao conectar com o banco de dados.</div>';
            return;
        }

        historicoNuvem = registros;

        if (registros.length === 0) {
            lista.innerHTML = '<div class="mensagem-vazia">Nenhuma análise encontrada no banco de dados.</div>';
            return;
        }

        lista.innerHTML = '';
        
        registros.forEach((item, index) => {
            const dataFormatada = new Date(item.data_analise).toLocaleString('pt-BR');

            const card = document.createElement('div');
            card.className = 'card-historico-item';
            card.innerHTML = `
                <div class="thumb-container">
                    <img src="${item.imagem_original}" alt="Imagem Analisada">
                </div>
                <div class="info-historico">
                    <span class="data-badge">${dataFormatada}</span>
                    <h4>${item.metodo}</h4>
                    <div class="badge-ia" style="width: fit-content; padding: 5px 10px; font-size: 0.8rem; margin-top: 5px;">
                        ${item.probabilidade}
                    </div>
                </div>
                <button class="btn-detalhes" onclick="verDetalhes(${index})">EXAMINAR RESULTADO</button>
            `;
            lista.appendChild(card);
        });
    };

    window.verDetalhes = (index) => {
        const item = historicoNuvem[index];
        document.getElementById('modalImgProcessada').src = item.resultado_img || item.imagem_original;
        document.getElementById('modalTitulo').innerText = `Método: ${item.metodo}`;
        modal.style.display = 'flex';
    };

    document.querySelector('.btn-fechar-modal').onclick = () => modal.style.display = 'none';
    window.onclick = (e) => { if (e.target == modal) modal.style.display = 'none'; };

    btnLimpar.onclick = async () => {
        if(confirm("Deseja apagar TODOS os seus registros periciais da nuvem? Esta ação é irreversível.")) {
            const { data: { user } } = await _supabase.auth.getUser();
            
            await _supabase
                .from('historico_analises')
                .delete()
                .eq('user_id', user.id); 
            
            location.reload();
        }
    };

    carregarHistorico();
});