from flask import Flask, render_template, jsonify
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Nome da planilha e suas páginas
spreadsheet_name = 'PLANILHAS CRM'
sheet_names = ['SMART POS - PIPE + TYPE', 'TAP TO PHONE', 'LEADS VENDAS KOMMO']

# Função para conectar ao Google Sheets
def conectar_google_sheets():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('myykanbanessencial-91210238cd8a.json', scope)
        client = gspread.authorize(creds)
        planilha = client.open(spreadsheet_name)
        return {sheet_name: planilha.worksheet(sheet_name) for sheet_name in sheet_names}
    except Exception as e:
        print(f"Erro ao conectar ao Google Sheets: {e}")
        return None

# Função para carregar os dados e organizá-los por funil e etapa
def carregar_clientes():
    sheets = conectar_google_sheets()
    if not sheets:
        return {}

    # Estrutura de armazenamento por funil e status
    funil_dados = {
        'SMART POS - PIPE + TYPE': {'Perdidos': [], 'Em Contato': [], 'Sem Contato': [], 'Fechados': []},
        'TAP TO PHONE': {'Perdidos': [], 'Em Contato': [], 'Sem Contato': [], 'Fechados': []},
        'LEADS VENDAS KOMMO': {'Perdidos': [], 'Em Contato': [], 'Sem Contato': [], 'Fechados': []}
    }

    try:
        for funil, sheet in sheets.items():
            print(f"Carregando dados do funil: {funil}")
            data = sheet.get_all_records(default_blank="")
            df = pd.DataFrame(data)

            # Definir colunas com base no funil atual
            if funil == 'LEADS VENDAS KOMMO':
                nome_coluna = 'Lead título'
                telefone_coluna = 'Telefone comercial (contato)'
                id_coluna = 'ID'
                status_coluna = 'Etapa do lead'
            elif funil == 'TAP TO PHONE':  # Ajuste para o funil TAP TO PHONE
                nome_coluna = 'Negócio - Pessoa de contato 2'  # Atualize este nome conforme o nome da coluna real no seu Google Sheets
                telefone_coluna_1 = 'TELEFONE - OPÇÃO 1'
                telefone_coluna_2 = 'TELEFONE - OPÇÃO 2'
                id_coluna = 'Negócio - ID'
                status_coluna = 'Negócio - Status'
            elif funil == 'SMART POS - PIPE + TYPE':
                nome_coluna = 'Negócio - Pessoa de contato'
                telefone_coluna_1 = 'TELEFONE - OPÇÃO 1'
                telefone_coluna_2 = 'TELEFONE - OPÇÃO 2'
                id_coluna = 'ID'
                status_coluna = 'Negócio - Status'

            # Iterar pelas linhas do DataFrame e processar cada cliente
            for _, row in df.iterrows():
                cliente = row.to_dict()

                # Extrair nome e telefone conforme as colunas definidas para cada funil
                nome_cliente = row.get(nome_coluna, 'Indefinido')
                telefone_cliente = row.get(telefone_coluna, 'Sem telefone') if funil == 'LEADS VENDAS KOMMO' else row.get(telefone_coluna_1, 'Sem telefone')

                # Caso não exista telefone na primeira coluna, buscar na segunda (se não for o funil do Kommo)
                if telefone_cliente in [None, '', 'Sem telefone'] and funil != 'LEADS VENDAS KOMMO':
                    telefone_cliente = row.get(telefone_coluna_2, 'Sem telefone')

                # Adicionar informações ao dicionário do cliente
                cliente['Nome'] = nome_cliente
                cliente['Telefone'] = telefone_cliente
                cliente['Funil'] = funil

                # Definir a etapa correta com base no status
                status = row.get(status_coluna, 'Indefinido')
                if status == 'Perdido':
                    funil_dados[funil]['Perdidos'].append(cliente)
                elif status in ['Aberto', 'coleta de informações']:
                    funil_dados[funil]['Em Contato'].append(cliente)
                elif status == 'TYPEFORM ENVIADO':
                    funil_dados[funil]['Sem Contato'].append(cliente)
                else:
                    funil_dados[funil]['Fechados'].append(cliente)

    except Exception as e:
        print(f"Erro ao carregar clientes: {e}")

    return funil_dados

@app.route('/')
def kanban():
    return render_template('kanban.html')

# Rota para carregar funil específico
@app.route('/funil/<funil_name>', methods=['GET'])
def carregar_funil(funil_name):
    clientes_funis = carregar_clientes()
    if funil_name in clientes_funis:
        return jsonify(clientes_funis[funil_name])
    else:
        return jsonify({"erro": "Funil não encontrado"}), 404

# Rota para obter informações detalhadas de um cliente específico com base no ID
@app.route('/cliente/<int:id>')
def detalhes_cliente(id):
    sheets = conectar_google_sheets()
    if not sheets:
        return jsonify({"erro": "Erro ao conectar ao Google Sheets"}), 500

    try:
        # Concatenar todos os dados de todas as abas
        df = pd.concat([pd.DataFrame(sheet.get_all_records(default_blank="")) for sheet in sheets.values()], ignore_index=True)

        # Identificar a coluna correta de ID
        id_column = 'Negócio - ID' if 'Negócio - ID' in df.columns else 'ID'

        cliente = df[df[id_column] == id]
        if cliente.empty:
            return jsonify({"erro": f"Cliente com ID {id} não encontrado"}), 404

        return jsonify(cliente.to_dict(orient='records')[0])

    except Exception as e:
        print(f"Erro ao obter detalhes do cliente: {e}")
        return jsonify({"erro": "Erro ao buscar informações do cliente"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
