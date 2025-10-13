# ... (início do arquivo)

# Adiciona estilos customizados com maior espaçamento e fontes maiores
st.markdown("""
<style>
    /* Força o tema escuro */
    .stApp {
        background-color: #0e1117; 
        color: #ffffff;
    }
    
    /* **AJUSTE FINAL: BORDA ARREDONDADA E FUNDO MAIS CLARO** */
    .game-card {
        padding: 20px; /* Aumenta o espaçamento interno do card */
        margin-bottom: 35px; /* Espaço entre as linhas de jogos (vertical) */
        
        /* Aplica a borda arredondada */
        border: 1px solid rgba(255, 255, 255, 0.25); 
        border-radius: 10px; /* Bordas mais arredondadas */
        
        /* Cor de fundo para destacar o card do fundo da página */
        background-color: #1c212a; 
        
        width: 100%; 
    }

    /* ... (restante dos estilos)
