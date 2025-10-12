# NOVO TRECHO DE CÓDIGO (Adicionar após load_data)

def process_for_win_loss_evolution(df_events):
    """Calcula as vitórias e derrotas acumuladas para cada time."""
    
    # 1. Filtra apenas jogos finalizados
    df_results = df_events[
        df_events['Status'].str.startswith('Finalizado', na=False)
    ].copy()
    
    if df_results.empty:
        return pd.DataFrame()
    
    # Prepara a lista de resultados no formato Time, Vitoria, Derrota
    evolution_data = []

    # Itera sobre cada resultado (o que pode ser lento para muitas linhas)
    for index, row in df_results.iterrows():
        casa = row['Casa']
        visitante = row['Visitante']
        vencedor = row['Vencedor']
        
        # Atribuição de W/L
        if vencedor == casa:
            evolution_data.append({'Time': casa, 'Jogo': row['Jogo'], 'Resultado': 'Vitória', 'Ordem': index})
            evolution_data.append({'Time': visitante, 'Jogo': row['Jogo'], 'Resultado': 'Derrota', 'Ordem': index})
        elif vencedor == visitante:
            evolution_data.append({'Time': visitante, 'Jogo': row['Jogo'], 'Resultado': 'Vitória', 'Ordem': index})
            evolution_data.append({'Time': casa, 'Jogo': row['Jogo'], 'Resultado': 'Derrota', 'Ordem': index})
        else:
            # Não faz nada para Empate/N/A, ou você pode adicionar a lógica de empate se necessário

    df_evo = pd.DataFrame(evolution_data)
    if df_evo.empty:
        return pd.DataFrame()
        
    # Transforma o resultado em colunas binárias (1=Vitória, 0=Derrota)
    df_evo['Vitória'] = (df_evo['Resultado'] == 'Vitória').astype(int)
    df_evo['Derrota'] = (df_evo['Resultado'] == 'Derrota').astype(int)
    
    # 2. Calcula o acumulado por time
    df_evo['Vitorias Acumuladas'] = df_evo.groupby('Time')['Vitória'].cumsum()
    df_evo['Derrotas Acumuladas'] = df_evo.groupby('Time')['Derrota'].cumsum()
    
    # Adiciona um índice de jogo para o eixo X do gráfico
    df_evo['Total Jogos'] = df_evo.groupby('Time').cumcount() + 1
    
    return df_evo


# NOVA FUNÇÃO DE PLOTAGEM (Adicionar dentro de main)
import altair as alt # Nova importação

def plot_win_loss_evolution(df_evo, selected_teams):
    """Cria o gráfico de evolução W/L."""
    if df_evo.empty:
        return st.warning("Não há dados de jogos finalizados para o gráfico.")

    # Filtra os times selecionados
    df_plot = df_evo[df_evo['Time'].isin(selected_teams)]
    
    # Gráfico de Linhas (Evolução de Vitórias)
    chart = alt.Chart(df_plot).mark_line(point=True).encode(
        x=alt.X('Total Jogos', axis=alt.Axis(title='Jogos Disputados')),
        y=alt.Y('Vitorias Acumuladas', axis=alt.Axis(title='Vitórias Acumuladas')),
        color='Time',
        tooltip=['Time', 'Jogo', 'Resultado', 'Vitorias Acumuladas', 'Derrotas Acumuladas']
    ).properties(
        title='Evolução de Vitórias Acumuladas'
    ).interactive()

    st.altair_chart(chart, use_container_width=True)
    
    # Gráfico de Área (Opcional - Total de W/L)
    st.markdown("---")
    st.subheader("Evolução de W-L")

    # Transforma o DataFrame para o formato 'long' para empilhamento no Altair
    df_long = pd.melt(
        df_plot, 
        id_vars=['Time', 'Total Jogos'], 
        value_vars=['Vitorias Acumuladas', 'Derrotas Acumuladas'],
        var_name='Métrica', 
        value_name='Contagem'
    )
    
    area_chart = alt.Chart(df_long).mark_area().encode(
        x=alt.X('Total Jogos', axis=alt.Axis(title='Jogos Disputados')),
        y=alt.Y('Contagem', stack=None, axis=alt.Axis(title='Vitórias/Derrotas')), # stack=None para sobrepor (não empilhar)
        color='Métrica',
        row='Time', # Divide o gráfico por time
        tooltip=['Time', 'Métrica', 'Contagem']
    ).properties(
        title='Vitórias vs Derrotas por Time'
    ).interactive()

    st.altair_chart(area_chart, use_container_width=True)
