import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests 
from dateutil.parser import isoparse 

# Configuração da página (Layout wide e Dark Mode forçado pelo CSS global)
st.set_page_config(
    page_title="NFL Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# --- 1. CONFIGURAÇÃO DE LOGOS E API ---

API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

# Mapeamento para garantir que abreviações sejam traduzidas corretamente para a URL do logo
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin", 
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb", 
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar", 
    "LV": "rai", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg", 
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten", 
    "WAS": "wsh", "ARI": "ari", "WSH": "wsh"
}

def get_logo_url(abbreviation):
    """Gera a URL do logo (500x500) para melhor resolução, ajustada via HTML."""
    abbr = LOGO_MAP.get(abbreviation.upper(), abbreviation.lower())
    # URL de assets da ESPN.
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"


# --- 2. FUNÇÕES DE PROCESSAMENTO DE DADOS ---

def get_period_name(period):
    """Mapeia o número do período para o nome do Quarto/Overtime."""
    if period == 1: return "1st Quarter"
    if period == 2: return "2nd Quarter"
    if period == 3: return "3rd Quarter"
    if period == 4: return "4th Quarter"
    if period > 4: return "OT"
    return ""

def get_event_data(event):
    """Extrai e formata os dados principais de um único evento."""
    
    data_formatada = "N/A"
    status_pt = "N/A"
    winner_team_abbr = "A definir"
    detail_status = "N/A" 
    home_team_abbr = "N/A"
    away_team_abbr = "N/A"
    
    try:
        comp = event['competitions'][0]
        date_iso = comp.get('date')

        if date_iso:
            try:
                dt_utc = isoparse(date_iso) 
                dt_brt = dt_utc - pd.Timedelta(hours=3) # Ajuste para Brasília

                data_formatada = dt_brt.strftime('%d/%m/%Y')
            except Exception:
                pass 

        status = comp.get('status', {}) 
        status_type = status.get('type', {})
        
        status_text_check = str(status_type).lower() 

        if 'final' in status_text_check:
            status_pt = 'Finalizado (OT)' if 'ot' in status_text_check or 'overtime' in status_text_check else 'Finalizado'
        elif status_type.get('state') == 'in':
            status_pt = 'Em Andamento'
        elif status_type.get('state') == 'pre':
            status_pt = 'Agendado'
        else:
            status_pt = status_type.get('description', 'Status Desconhecido') 
        
        detail_status = status.get('detail', status_type.get('shortDetail', 'N/A'))
        
        # Formatação de Status Aprimorada
        if status_pt == 'Em Andamento':
            clock = status.get('displayClock', '')
            period_name = get_period_name(status.get('period', 0))
            if clock and period_name:
                detail_status = f"{period_name} - {clock}" # Ex: 4th Quarter - 14:18
            else:
                detail_status = status_type.get('shortDetail', 'Ao Vivo')
            
        elif status_pt == 'Finalizado' or status_pt == 'Finalizado (OT)':
            detail_status = status_type.get('shortDetail', 'Final')
            
        elif status_pt == 'Agendado':
            dt_utc = isoparse(date_iso) 
            dt_brt = dt_utc - pd.Timedelta(hours=3)
            detail_status = dt_brt.strftime('%H:%M BRT') # Ex: 20:20 BRT
            
        
        competitors = comp.get('competitors', [])
        home_team = {} 
        away_team = {} 

        if len(competitors) >= 2:
            c1 = competitors[0]
            c2 = competitors[1]
            
            if c1.get('homeAway') == 'home':
                home_team, away_team = c1, c2
            elif c2.get('homeAway') == 'home':
                home_team, away_team = c2, c1
            else:
                home_team, away_team = c1, c2
                
        # Garante que o score é um número
        home_score = int(home_team.get('score', {}).get('value', 0.0))
        away_score = int(away_team.get('score', {}).get('value', 0.0))
        
        home_team_abbr = home_team.get('team', {}).get('abbreviation', 'CASA')
        away_team_abbr = away_team.get('team', {}).get('abbreviation', 'FORA')
            
        if status_pt.startswith('Finalizado'):
            if home_score > away_score:
                winner_team_abbr = home_team_abbr
            elif away_score > home_score:
                winner_team_abbr = away_team_abbr
            else:
                winner_team_abbr = "Empate"


        return {
            'Jogo': event.get('name', 'N/A'),
            'Data': data_formatada,
            'Status': status_pt, 
            'Casa': home_team_abbr,
            'Visitante': away_team_abbr,
            'Vencedor': winner_team_abbr,
            'Score Casa': home_score,
            'Score Visitante': away_score,
            'Detalhe Status': detail_status,
        }
        
    except Exception:
        # Fallback de erro
        return {
            'Jogo': 'Erro de Estrutura de Dados', 'Data': 'N/A',
            'Status': 'ERRO', 'Casa': 'ERRO', 'Visitante': 'ERRO',
            'Vencedor': 'N/A', 'Score Casa': 'N/A', 'Score Visitante': 'N/A',
            'Detalhe Status': 'Falha na extração',
        }


def load_data(api_url=API_URL_EVENTS_2025):
    """Busca dados localmente ou na API."""
    
    # Simula o carregamento do arquivo JSON do ambiente
    json_content = """
    {"events":[{"id":"401772859","date":"2025-10-12T20:05Z","name":"Tennessee Titans at Las Vegas Raiders","shortName":"TEN @ LV","timeValid":true,"competitions":[{"id":"401772859","date":"2025-10-12T20:05Z","attendance":0,"dateValid":true,"neutralSite":false,"onWatchESPN":false,"wallclockAvailable":true,"highlightsAvailable":true,"competitors":[{"id":"13","type":"team","order":0,"homeAway":"home","team":{"id":"13","location":"Las Vegas","name":"Raiders","abbreviation":"LV","displayName":"Las Vegas Raiders","shortDisplayName":"Raiders","color":"000000","alternateColor":"a5acaf"},"score":{"value":17.0,"displayValue":"17"},"record":{"name":"overall","displayValue":"1-4"},"displayOrder":2},{"id":"10","type":"team","order":1,"homeAway":"away","team":{"id":"10","location":"Tennessee","name":"Titans","abbreviation":"TEN","displayName":"Tennessee Titans","shortDisplayName":"Titans","color":"4b92db","alternateColor":"002a5c"},"score":{"value":3.0,"displayValue":"3"},"record":{"name":"overall","displayValue":"1-4"},"displayOrder":1}],"notes":[],"status":{"clock":858.0,"displayClock":"14:18","period":4,"type":{"id":"2","name":"STATUS_IN_PROGRESS","state":"in","completed":false,"description":"In Progress","detail":"14:18 - 4th Quarter","shortDetail":"14:18 - 4th"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-12T20:05Z","timeValid":true,"displayValue":"4:05 ET"}}]},{"id":"401772752","date":"2025-10-12T20:25Z","name":"Cincinnati Bengals at Green Bay Packers","shortName":"CIN @ GB","timeValid":true,"competitions":[{"id":"401772752","date":"2025-10-12T20:25Z","attendance":0,"dateValid":true,"neutralSite":false,"onWatchESPN":false,"wallclockAvailable":true,"highlightsAvailable":true,"competitors":[{"id":"9","type":"team","order":0,"homeAway":"home","team":{"id":"9","location":"Green Bay","name":"Packers","abbreviation":"GB","displayName":"Green Bay Packers","shortDisplayName":"Packers","color":"204e32","alternateColor":"ffb612"},"score":{"value":10.0,"displayValue":"10"},"record":{"name":"overall","displayValue":"2-1-1"},"displayOrder":2},{"id":"4","type":"team","order":1,"homeAway":"away","team":{"id":"4","location":"Cincinnati","name":"Bengals","abbreviation":"CIN","displayName":"Cincinnati Bengals","shortDisplayName":"Bengals","color":"fb4f14","alternateColor":"000000"},"score":{"value":0.0,"displayValue":"0"},"record":{"name":"overall","displayValue":"2-3"},"displayOrder":1}],"notes":[],"status":{"clock":379.0,"displayClock":"6:19","period":3,"type":{"id":"2","name":"STATUS_IN_PROGRESS","state":"in","completed":false,"description":"In Progress","detail":"6:19 - 3rd Quarter","shortDetail":"6:19 - 3rd"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-12T20:25Z","timeValid":true,"displayValue":"4:25 ET"}}]},{"id":"401772749","date":"2025-10-12T20:25Z","name":"San Francisco 49ers at Tampa Bay Buccaneers","shortName":"SF @ TB","timeValid":true,"competitions":[{"id":"401772749","date":"2025-10-12T20:25Z","attendance":0,"dateValid":true,"neutralSite":false,"onWatchESPN":false,"wallclockAvailable":true,"highlightsAvailable":true,"competitors":[{"id":"27","type":"team","order":0,"homeAway":"home","team":{"id":"27","location":"Tampa Bay","name":"Buccaneers","abbreviation":"TB","displayName":"Tampa Bay Buccaneers","shortDisplayName":"Buccaneers","color":"bd1c36","alternateColor":"3e3a35"},"score":{"value":20.0,"displayValue":"20"},"record":{"name":"overall","displayValue":"4-1"},"displayOrder":2},{"id":"25","type":"team","order":1,"homeAway":"away","team":{"id":"25","location":"San Francisco","name":"49ers","abbreviation":"SF","displayName":"San Francisco 49ers","shortDisplayName":"49ers","color":"aa0000","alternateColor":"b3995d"},"score":{"value":16.0,"displayValue":"16"},"record":{"name":"overall","displayValue":"4-1"},"displayOrder":1}],"notes":[],"status":{"clock":778.0,"displayClock":"12:58","period":3,"type":{"id":"2","name":"STATUS_IN_PROGRESS","state":"in","completed":false,"description":"In Progress","detail":"12:58 - 3rd Quarter","shortDetail":"12:58 - 3rd"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-12T20:25Z","timeValid":true,"displayValue":"4:25 ET"}}]},{"id":"401772634","date":"2025-10-12T13:30Z","name":"Denver Broncos at New York Jets","shortName":"DEN VS NYJ","timeValid":true,"competitions":[{"id":"401772634","date":"2025-10-12T13:30Z","attendance":61155,"dateValid":true,"neutralSite":true,"onWatchESPN":false,"wallclockAvailable":true,"highlightsAvailable":true,"competitors":[{"id":"20","type":"team","order":0,"homeAway":"home","winner":false,"team":{"id":"20","location":"New York","name":"Jets","abbreviation":"NYJ","displayName":"New York Jets","shortDisplayName":"Jets","color":"115740","alternateColor":"ffffff"},"score":{"value":11.0,"displayValue":"11","winner":false},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"0-6"},"displayOrder":2},{"id":"7","type":"team","order":1,"homeAway":"away","winner":true,"team":{"id":"7","location":"Denver","name":"Broncos","abbreviation":"DEN","displayName":"Denver Broncos","shortDisplayName":"Broncos","color":"0a2343","alternateColor":"fc4c02"},"score":{"value":13.0,"displayValue":"13","winner":true},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"4-2"},"displayOrder":1}],"notes":[{"type":"event","headline":"NFL London Games"}],"status":{"clock":0.0,"displayClock":"0:00","period":4,"type":{"id":"3","name":"STATUS_FINAL","state":"post","completed":true,"description":"Final","detail":"Final","shortDetail":"Final"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-12T13:30Z","timeValid":true,"displayValue":"9:30 AM ET"}}]},{"id":"401772856","date":"2025-10-12T17:00Z","name":"Arizona Cardinals at Indianapolis Colts","shortName":"ARI @ IND","timeValid":true,"competitions":[{"id":"401772856","date":"2025-10-12T17:00Z","attendance":65523,"dateValid":true,"neutralSite":false,"onWatchESPN":false,"wallclockAvailable":true,"highlightsAvailable":true,"competitors":[{"id":"11","type":"team","order":0,"homeAway":"home","winner":true,"team":{"id":"11","location":"Indianapolis","name":"Colts","abbreviation":"IND","displayName":"Indianapolis Colts","shortDisplayName":"Colts","color":"003b75","alternateColor":"ffffff"},"score":{"value":31.0,"displayValue":"31","winner":true},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"5-1"},"displayOrder":2},{"id":"22","type":"team","order":1,"homeAway":"away","winner":false,"team":{"id":"22","location":"Arizona","name":"Cardinals","abbreviation":"ARI","displayName":"Arizona Cardinals","shortDisplayName":"Cardinals","color":"a40227","alternateColor":"ffffff"},"score":{"value":27.0,"displayValue":"27","winner":false},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"2-4"},"displayOrder":1}],"notes":[],"status":{"clock":0.0,"displayClock":"0:00","period":4,"type":{"id":"3","name":"STATUS_FINAL","state":"post","completed":true,"description":"Final","detail":"Final","shortDetail":"Final"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-12T17:00Z","timeValid":true,"displayValue":"1 ET"}}]},{"id":"401772750","date":"2025-10-12T17:00Z","name":"Los Angeles Chargers at Miami Dolphins","shortName":"LAC @ MIA","timeValid":true,"competitions":[{"id":"401772750","date":"2025-10-12T17:00Z","attendance":65592,"dateValid":true,"neutralSite":false,"onWatchESPN":false,"wallclockAvailable":true,"highlightsAvailable":true,"competitors":[{"id":"15","type":"team","order":0,"homeAway":"home","winner":false,"team":{"id":"15","location":"Miami","name":"Dolphins","abbreviation":"MIA","displayName":"Miami Dolphins","shortDisplayName":"Dolphins","color":"008e97","alternateColor":"fc4c02"},"score":{"value":27.0,"displayValue":"27","winner":false},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"1-5"},"displayOrder":2},{"id":"24","type":"team","order":1,"homeAway":"away","winner":true,"team":{"id":"24","location":"Los Angeles","name":"Chargers","abbreviation":"LAC","displayName":"Los Angeles Chargers","shortDisplayName":"Chargers","color":"0080c6","alternateColor":"ffc20e"},"score":{"value":29.0,"displayValue":"29","winner":true},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"4-2"},"displayOrder":1}],"notes":[],"status":{"clock":0.0,"displayClock":"0:00","period":4,"type":{"id":"3","name":"STATUS_FINAL","state":"post","completed":true,"description":"Final","detail":"Final","shortDetail":"Final"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-12T17:00Z","timeValid":true,"displayValue":"1 ET"}}]},{"id":"401772751","date":"2025-10-12T17:00Z","name":"New England Patriots at New Orleans Saints","shortName":"NE @ NO","timeValid":true,"competitions":[{"id":"401772751","date":"2025-10-12T17:00Z","attendance":70042,"dateValid":true,"neutralSite":false,"onWatchESPN":false,"wallclockAvailable":true,"highlightsAvailable":true,"competitors":[{"id":"18","type":"team","order":0,"homeAway":"home","winner":false,"team":{"id":"18","location":"New Orleans","name":"Saints","abbreviation":"NO","displayName":"New Orleans Saints","shortDisplayName":"Saints","color":"d3bc8d","alternateColor":"000000"},"score":{"value":19.0,"displayValue":"19","winner":false},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"1-5"},"displayOrder":2},{"id":"17","type":"team","order":1,"homeAway":"away","winner":true,"team":{"id":"17","location":"New England","name":"Patriots","abbreviation":"NE","displayName":"New England Patriots","shortDisplayName":"Patriots","color":"002a5c","alternateColor":"c60c30"},"score":{"value":25.0,"displayValue":"25","winner":true},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"4-2"},"displayOrder":1}],"notes":[],"status":{"clock":0.0,"displayClock":"0:00","period":4,"type":{"id":"3","name":"STATUS_FINAL","state":"post","completed":true,"description":"Final","detail":"Final","shortDetail":"Final"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-12T17:00Z","timeValid":true,"displayValue":"1 ET"}}]},{"id":"401772748","date":"2025-10-12T17:00Z","name":"Cleveland Browns at Pittsburgh Steelers","shortName":"CLE @ PIT","timeValid":true,"competitions":[{"id":"401772748","date":"2025-10-12T17:00Z","attendance":66738,"dateValid":true,"neutralSite":false,"onWatchESPN":false,"wallclockAvailable":true,"highlightsAvailable":true,"competitors":[{"id":"23","type":"team","order":0,"homeAway":"home","winner":true,"team":{"id":"23","location":"Pittsburgh","name":"Steelers","abbreviation":"PIT","displayName":"Pittsburgh Steelers","shortDisplayName":"Steelers","color":"000000","alternateColor":"ffb612"},"score":{"value":23.0,"displayValue":"23","winner":true},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"4-1"},"displayOrder":2},{"id":"5","type":"team","order":1,"homeAway":"away","winner":false,"team":{"id":"5","location":"Cleveland","name":"Browns","abbreviation":"CLE","displayName":"Cleveland Browns","shortDisplayName":"Browns","color":"472a08","alternateColor":"ff3c00"},"score":{"value":9.0,"displayValue":"9","winner":false},"record":{"name":"overall","displayValue":"1-5"},"displayOrder":1}],"notes":[],"status":{"clock":0.0,"displayClock":"0:00","period":4,"type":{"id":"3","name":"STATUS_FINAL","state":"post","completed":true,"description":"Final","detail":"Final","shortDetail":"Final"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-12T17:00Z","timeValid":true,"displayValue":"1 ET"}}]},{"id":"401772858","date":"2025-10-12T17:00Z","name":"Dallas Cowboys at Carolina Panthers","shortName":"DAL @ CAR","timeValid":true,"competitions":[{"id":"401772858","date":"2025-10-12T17:00Z","attendance":71619,"dateValid":true,"neutralSite":false,"onWatchESPN":false,"wallclockAvailable":true,"highlightsAvailable":true,"competitors":[{"id":"29","type":"team","order":0,"homeAway":"home","winner":true,"team":{"id":"29","location":"Carolina","name":"Panthers","abbreviation":"CAR","displayName":"Carolina Panthers","shortDisplayName":"Panthers","color":"0085ca","alternateColor":"000000"},"score":{"value":30.0,"displayValue":"30","winner":true},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"3-3"},"displayOrder":2},{"id":"6","type":"team","order":1,"homeAway":"away","winner":false,"team":{"id":"6","location":"Dallas","name":"Cowboys","abbreviation":"DAL","displayName":"Dallas Cowboys","shortDisplayName":"Cowboys","color":"002a5c","alternateColor":"b0b7bc"},"score":{"value":27.0,"displayValue":"27","winner":false},"record":{"name":"overall","displayValue":"2-3-1"},"displayOrder":1}],"notes":[],"status":{"clock":0.0,"displayClock":"0:00","period":4,"type":{"id":"3","name":"STATUS_FINAL","state":"post","completed":true,"description":"Final","detail":"Final","shortDetail":"Final"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-12T17:00Z","timeValid":true,"displayValue":"1 ET"}}]},{"id":"401772857","date":"2025-10-12T17:00Z","name":"Seattle Seahawks at Jacksonville Jaguars","shortName":"SEA @ JAX","timeValid":true,"competitions":[{"id":"401772857","date":"2025-10-12T17:00Z","attendance":61056,"dateValid":true,"neutralSite":false,"onWatchESPN":false,"wallclockAvailable":true,"highlightsAvailable":true,"competitors":[{"id":"30","type":"team","order":0,"homeAway":"home","winner":false,"team":{"id":"30","location":"Jacksonville","name":"Jaguars","abbreviation":"JAX","displayName":"Jacksonville Jaguars","shortDisplayName":"Jaguars","color":"007487","alternateColor":"d7a22a"},"score":{"value":12.0,"displayValue":"12","winner":false},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"4-2"},"displayOrder":2},{"id":"26","type":"team","order":1,"homeAway":"away","winner":true,"team":{"id":"26","location":"Seattle","name":"Seahawks","abbreviation":"SEA","displayName":"Seattle Seahawks","shortDisplayName":"Seahawks","color":"002a5c","alternateColor":"69be28"},"score":{"value":20.0,"displayValue":"20","winner":true},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"4-2"},"displayOrder":1}],"notes":[],"status":{"clock":0.0,"displayClock":"0:00","period":4,"type":{"id":"3","name":"STATUS_FINAL","state":"post","completed":true,"description":"Final","detail":"Final","shortDetail":"Final"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-12T17:00Z","timeValid":true,"displayValue":"1 ET"}}]},{"id":"401772855","date":"2025-10-12T17:00Z","name":"Los Angeles Rams at Baltimore Ravens","shortName":"LAR @ BAL","timeValid":true,"competitions":[{"id":"401772855","date":"2025-10-12T17:00Z","attendance":70055,"dateValid":true,"neutralSite":false,"onWatchESPN":false,"wallclockAvailable":true,"highlightsAvailable":true,"competitors":[{"id":"33","type":"team","order":0,"homeAway":"home","winner":false,"team":{"id":"33","location":"Baltimore","name":"Ravens","abbreviation":"BAL","displayName":"Baltimore Ravens","shortDisplayName":"Ravens","color":"29126f","alternateColor":"000000"},"score":{"value":3.0,"displayValue":"3","winner":false},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"1-5"},"displayOrder":2},{"id":"14","type":"team","order":1,"homeAway":"away","winner":true,"team":{"id":"14","location":"Los Angeles","name":"Rams","abbreviation":"LAR","displayName":"Los Angeles Rams","shortDisplayName":"Rams","color":"003594","alternateColor":"ffd100"},"score":{"value":17.0,"displayValue":"17","winner":true},"record":{"name":"overall","displayName":"Record Year To Date","displayValue":"4-2"},"displayOrder":1}],"notes":[],"status":{"clock":0.0,"displayClock":"0:00","period":4,"type":{"id":"3","name":"STATUS_FINAL","state":"post","completed":true,"description":"Final","detail":"Final","shortDetail":"Final"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-12T17:00Z","timeValid":true,"displayValue":"1 ET"}}]},{"id":"401772923","date":"2025-10-13T00:20Z","name":"Detroit Lions at Kansas City Chiefs","shortName":"DET @ KC","timeValid":true,"competitions":[{"id":"401772923","date":"2025-10-13T00:20Z","attendance":0,"dateValid":true,"neutralSite":false,"onWatchESPN":false,"wallclockAvailable":false,"highlightsAvailable":true,"competitors":[{"id":"12","type":"team","order":0,"homeAway":"home","team":{"id":"12","location":"Kansas City","name":"Chiefs","abbreviation":"KC","displayName":"Kansas City Chiefs","shortDisplayName":"Chiefs","color":"e31837","alternateColor":"ffb612"},"score":{"value":0.0,"displayValue":"0"},"record":{"name":"overall","displayValue":"2-3"},"displayOrder":2},{"id":"8","type":"team","order":1,"homeAway":"away","team":{"id":"8","location":"Detroit","name":"Lions","abbreviation":"DET","displayName":"Detroit Lions","shortDisplayName":"Lions","color":"0076b6","alternateColor":"bbbbbb"},"score":{"value":0.0,"displayValue":"0"},"record":{"name":"overall","displayValue":"4-1"},"displayOrder":1}],"notes":[],"status":{"clock":0.0,"displayClock":"0:00","period":0,"type":{"id":"1","name":"STATUS_SCHEDULED","state":"pre","completed":false,"description":"Scheduled","detail":"Sun, October 12th at 8:20 PM EDT","shortDetail":"10/12 - 8:20 PM EDT"}},"format":{"regulation":{"periods":4,"displayName":"Quarter","slug":"quarter","clock":900.0},"overtime":{"periods":1,"displayName":"sudden-death","slug":"sudden-death","clock":600.0}},"hasDefensiveStats":false,"time":{"value":"2025-10-13T00:20Z","timeValid":true,"displayValue":"8:20 ET"}}]}
    """ # Conteúdo do events (1).json truncado para o essencial
    
    try:
        data = json.loads(json_content)
    except json.JSONDecodeError:
        # Fallback para a API caso o JSON fornecido esteja vazio/corrompido
        try:
            response = requests.get(api_url)
            response.raise_for_status() 
            data = response.json()
        except requests.exceptions.RequestException:
            st.error(f"Erro ao buscar dados da API. Verifique a URL e autenticação.")
            return pd.DataFrame()

    events_list = data.get('events', [])
    events_data = [get_event_data(e) for e in events_list]
    events_data = [item for item in events_data if item is not None]
        
    if not events_data:
        return pd.DataFrame()
        
    df = pd.DataFrame(events_data)
    return df

# --- 3. FUNÇÃO DE RENDERIZAÇÃO CUSTOMIZADA (GRID 3x1) ---

def display_final_results_styled(df_finalized):
    """
    Renderiza os resultados finais em um layout de 3 cards por linha, 
    extremamente compacto e com destaque para o vencedor.
    """
    
    rows = [row for index, row in df_finalized.iterrows()]
    
    # CSS injetado para o Dark Mode e estilo do Card, ajustado para ser o mais compacto
    st.markdown("""
        <style>
            .stApp {
                background-color: #0E1117; /* Fundo principal do app */
            }
            .nfl-card {
                background-color: #282A36; 
                border-radius: 10px; 
                padding: 10px 12px; /* Padding ajustado */
                margin: 5px 0; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                color: #FAFAFA;
                /* Max-width para garantir que em telas grandes o card não fique exagerado */
                max-width: 350px; 
            }
            .nfl-date-status {
                font-size: 11px;
                color: #B0B0B0; 
                text-align: center;
                margin-bottom: 8px !important;
                border-bottom: 1px solid #333;
                padding-bottom: 5px;
            }
            .nfl-team-block {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px; /* Espaçamento entre as linhas dos times */
            }
            .nfl-team-info {
                display: flex;
                align-items: center;
            }
            .nfl-score {
                font-size: 22px;
                font-weight: 500;
                color: #888888; /* Placar perdedor em cinza mais suave */
            }
            /* Destaque CRÍTICO para o Vencedor */
            .nfl-score-winner {
                font-size: 24px; /* Levemente maior */
                font-weight: 900; /* Negrito máximo */
                color: #69be28; /* Verde Google */
            }
            .nfl-abbr {
                font-size: 13px; /* Nome maior */
                font-weight: 600;
                color: #FAFAFA;
                margin-left: 10px;
                text-overflow: ellipsis;
                white-space: nowrap;
                overflow: hidden;
                width: 70px; /* Garante que o nome não quebre o layout */
            }
            .nfl-footer {
                font-size: 10px;
                color: #B0B0B0;
                text-align: center;
                margin-top: 5px;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Processa em grupos de 3 para o layout de colunas
    for i in range(0, len(rows), 3):
        
        # Cria as colunas com um pequeno espaçamento para compactação
        cols = st.columns(3, gap="small")
        chunk = rows[i:i+3]
        
        for j, row in enumerate(chunk):
            with cols[j]:
                
                is_home_winner = row['Vencedor'] == row['Casa']
                is_away_winner = row['Vencedor'] == row['Visitante']
                
                # Definir Status do Detalhe
                if row['Status'] == 'Agendado':
                    status_display = f'⏰ {row["Data"]} | {row["Detalhe Status"]}'
                elif row['Status'] == 'Em Andamento':
                    status_display = f'🔴 AO VIVO | {row["Detalhe Status"]}'
                else: # Finalizado
                    status_display = f'✅ {row["Detalhe Status"]}'
                
                
                # --- START CARD ---
                st.markdown('<div class="nfl-card">', unsafe_allow_html=True)

                # 1. Data/Status
                st.markdown(f'<p class="nfl-date-status">{status_display}</p>', unsafe_allow_html=True)

                # 2. Time Visitante
                away_score_class = "nfl-score-winner" if is_away_winner else "nfl-score"
                st.markdown(
                    f"""
                    <div class="nfl-team-block">
                        <div class="nfl-team-info">
                            <img src="{get_logo_url(row['Visitante'])}" width="30" height="30" style="margin-right: 5px;">
                            <span class="nfl-abbr">{row['Visitante']}</span>
                        </div>
                        <span class="{away_score_class}">{row["Score Visitante"]}</span>
                    </div>
                    """, unsafe_allow_html=True
                )
                
                # 3. Time Casa
                home_score_class = "nfl-score-winner" if is_home_winner else "nfl-score"
                st.markdown(
                    f"""
                    <div class="nfl-team-block">
                        <div class="nfl-team-info">
                            <img src="{get_logo_url(row['Casa'])}" width="30" height="30" style="margin-right: 5px;">
                            <span class="nfl-abbr">{row['Casa']}</span>
                        </div>
                        <span class="{home_score_class}">{row["Score Casa"]}</span>
                    </div>
                    """, unsafe_allow_html=True
                )
                
                # 4. Rodapé (Nome Completo do Jogo)
                st.markdown(f'<p class="nfl-footer">{row["Jogo"]}</p>', unsafe_allow_html=True)
                
                # --- END CARD ---
                st.markdown('</div>', unsafe_allow_html=True)
                
# --- 4. LAYOUT DO DASHBOARD STREAMLIT (MAIN) ---

def main():
    
    # Injeta CSS Global para o fundo e CENTRALIZAÇÃO DE TEXTOS
    st.markdown("""
        <style>
            /* Centraliza H1 (Título Principal) */
            h1 {
                text-align: center;
                padding-top: 0px !important;
                margin-top: 0px !important;
            }
            /* Centraliza H2 (Títulos das Seções) */
            h2 {
                text-align: center;
                margin-bottom: 0.5rem; /* Ajusta o espaçamento abaixo do H2 */
            }
            .css-1d3f0g2 { /* Classe Streamlit para containers (ajusta padding superior) */
                padding-top: 2rem; 
            }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("🏈 Resultados da NFL")
    
    df_events = load_data() 

    if df_events.empty:
        st.error("Não foi possível carregar os dados. Verifique a fonte de dados (JSON ou API).")
        return

    # st.markdown("---") <--- REMOVIDO para eliminar a barra
    
    # --- JOGOS AO VIVO (EM ANDAMENTO) ---
    
    st.header("🔴 Ao Vivo")
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento'].sort_values(by='Data', ascending=False)
    
    if not df_in_progress.empty:
        display_final_results_styled(df_in_progress)
    else:
        st.markdown('<p style="color:#888; text-align: center;">Nenhum jogo em andamento no momento.</p>', unsafe_allow_html=True)

    # st.markdown("---") <--- REMOVIDO para eliminar a barra

    # --- RESULTADOS FINAIS ---
    
    st.header("✅ Finalizados")
    df_finalized = df_events[
        df_events['Status'].str.startswith('Finalizado', na=False)
    ].sort_values(by='Data', ascending=False)
    
    if not df_finalized.empty:
        display_final_results_styled(df_finalized)
    else:
        st.markdown('<p style="color:#888; text-align: center;">Nenhum resultado finalizado encontrado.</p>', unsafe_allow_html=True)
        
    # st.markdown("---") <--- REMOVIDO para eliminar a barra
    
    # --- JOGOS AGENDADOS ---
    st.header("⏳ Agendados")
    df_scheduled = df_events[
        df_events['Status'] == 'Agendado'
    ].sort_values(by='Data', ascending=True)
    
    if not df_scheduled.empty:
        display_final_results_styled(df_scheduled)
    else:
        st.markdown('<p style="color:#888; text-align: center;">Nenhum jogo agendado nos dados fornecidos.</p>', unsafe_allow_html=True)


if __name__ == '__main__':
    main()
