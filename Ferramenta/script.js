document.addEventListener('DOMContentLoaded', () => {
    const btnAcaoSelecionar = document.getElementById('btnAcaoSelecionar');
    const inputFileBotao = document.getElementById('inputFileBotao');

    if (btnAcaoSelecionar && inputFileBotao) {
        btnAcaoSelecionar.addEventListener('click', () => {
            inputFileBotao.click();
        });

        inputFileBotao.addEventListener('change', () => {
            const arquivo = inputFileBotao.files[0];
            if (arquivo) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    localStorage.setItem('AIDA_ImagemSelecionada', e.target.result);
                    window.location.href = "../Ferramenta-Analise/index-analise.html"; 
                };
                reader.readAsDataURL(arquivo);
            }
        });
    }
});