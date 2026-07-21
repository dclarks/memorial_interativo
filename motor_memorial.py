# -*- coding: utf-8 -*-
import math
import os
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                                 QPushButton, QMessageBox, QFileDialog, QTableWidget, 
                                 QTableWidgetItem, QHeaderView, QSpinBox, QGroupBox, QFormLayout)
from qgis.PyQt.QtCore import Qt, pyqtSignal, QEventLoop, QVariant, QRectF
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsMapToolIdentifyFeature, QgsRubberBand
from qgis.core import (QgsProject, QgsField, QgsGeometry, QgsVectorLayer, QgsWkbTypes, 
                       QgsPointXY, QgsRectangle, QgsFeature, QgsPalLayerSettings, 
                       QgsTextFormat, QgsVectorLayerSimpleLabeling, Qgis)
from qgis.utils import iface

# --- MEMÓRIA GLOBAL DE VÉRTICES E DADOS PERSISTENTES ---
MEMORIA_COORDENADAS = {}
DADOS_ULTIMO_PROCESSAMENTO = {
    "raw_data": None,
    "reordered": None,
    "lista_confrontantes": None,
    "area_real": None,
    "centroide": None
}

# --- FUNÇÕES DINÂMICAS DE FORMATAÇÃO TOPOGRÁFICA ---
def formata_coordenada(valor, casas=3):
    """Formatador dinâmico de coordenadas UTM SEM separador de milhar"""
    texto = f"{valor:.{casas}f}"
    return texto.replace(".", ",")

def formata_distancia(valor, casas=2):
    """Formatador dinâmico de distâncias"""
    texto = f"{valor:.{casas}f}"
    return texto.replace(".", ",")

def formata_area(valor):
    """Formatador para Área: Padrão brasileiro com separador de milhar e 2 casas decimais"""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formata_azimute(az_dec, casas_segundos=0):
    """Converte azimute decimal para GMS com precisão configurável nos segundos"""
    d = int(az_dec)
    m = int((az_dec - d) * 60)
    s = (az_dec - d - m / 60.0) * 3600.0
    
    if round(s, casas_segundos) >= 60.0:
        s -= 60.0
        m += 1
        if m >= 60:
            m -= 60
            d = (d + 1) % 360

    if casas_segundos == 0:
        str_s = f"{int(round(s)):02d}"
    else:
        str_s = f"{s:0{3+casas_segundos}.{casas_segundos}f}".replace(".", ",")

    return f"{d}°{m:02d}'{str_s}\""


def gerar_tabela_e_desenho_dxf(dados_tabela, nodes, confrontantes, area_txt, centroide, caminho_arquivo):
    """Exporta a tabela compacta, poligonal, confrontantes e área no DXF com acentuação e m² perfeitos."""
    pontos_base = nodes[:-1] if nodes[0] == nodes[-1] else nodes
    xs = [p.x() for p in pontos_base]
    ys = [p.y() for p in nodes]
    max_x = max(xs)
    max_y = max(ys)
    
    largura_lote = max_x - min(xs)
    altura_lote = max_y - min(ys)
    dimensao_referencia = max(largura_lote, altura_lote)
    
    fator_escala = dimensao_referencia / 160.0
    if fator_escala < 0.1: fator_escala = 0.1
    if fator_escala > 50.0: fator_escala = 50.0  
    
    tab_x = max_x + (20 * fator_escala) 
    tab_y = max_y
    
    h6 = 7.5 * fator_escala
    h12 = 15.0 * fator_escala
    h18 = 22.5 * fator_escala
    h2 = 2.2 * fator_escala
    
    txt_tam_titulo = 2.8 * fator_escala   
    txt_tam_dados = 2.2 * fator_escala    
    
    c0 = 0.0
    c1 = 14.0 * fator_escala   
    c2 = 28.0 * fator_escala   
    c3 = 60.0 * fator_escala   
    c4 = 88.0 * fator_escala   
    c5 = 118.0 * fator_escala  
    c6 = 148.0 * fator_escala  

    pad_esquerd0 = 1.2 * fator_escala

    dxf = [
        "0", "SECTION",
        "2", "HEADER",
        "9", "$ACADVER", "1", "AC1009",
        "0", "ENDSEC",
        "0", "SECTION",
        "2", "TABLES",
        "0", "TABLE", "2", "LAYER", "70", "5",
        "0", "LAYER", "2", "Tabela", "70", "0", "62", "7", "6", "CONTINUOUS",
        "0", "LAYER", "2", "_PONTOS_DO_PROJETO", "70", "0", "62", "7", "6", "CONTINUOUS",
        "0", "LAYER", "2", "_POLIGONAL", "70", "0", "62", "7", "6", "CONTINUOUS",
        "0", "LAYER", "2", "_CONFRONTANTES", "70", "0", "62", "8", "6", "CONTINUOUS", 
        "0", "LAYER", "2", "_TEXTO_CENTRAL", "70", "0", "62", "1", "6", "CONTINUOUS",
        "0", "ENDTAB",
        "0", "TABLE", "2", "STYLE", "70", "1",
        "0", "STYLE", "2", "STANDARD", "70", "0", "40", "0.0", "41", "1.0", "50", "0.0", "71", "0", "42", "2.0", "3", "arial.ttf", "4", "",
        "0", "ENDTAB",
        "0", "ENDSEC",
        "0", "SECTION",
        "2", "BLOCKS",
        "0", "ENDSEC",
        "0", "SECTION",
        "2", "ENTITIES"
    ]

    def add_line(x1, y1, x2, y2, layer="Tabela"):
        dxf.extend([
            "0", "LINE",
            "8", layer,
            "10", f"{x1:.4f}", "20", f"{y1:.4f}", "30", "0.0",
            "11", f"{x2:.4f}", "21", f"{y2:.4f}", "31", "0.0"
        ])

    def sanitizar_dxf_unicode(texto):
        r"""Converte acentos e símbolos para sequências de escape Unicode do DXF"""
        mapa = {
            '°': '%%d',
            '²': '\\U+00B2',
            'Á': '\\U+00C1', 'Â': '\\U+00C2', 'Ã': '\\U+00C3', 'À': '\\U+00C0',
            'É': '\\U+00C9', 'Ê': '\\U+00CA',
            'Í': '\\U+00CD',
            'Ó': '\\U+00D3', 'Ô': '\\U+00D4', 'Õ': '\\U+00D5',
            'Ú': '\\U+00DA', 'Ü': '\\U+00DC',
            'Ç': '\\U+00C7',
            'á': '\\U+00E1', 'â': '\\U+00E2', 'ã': '\\U+00E3', 'à': '\\U+00E0',
            'é': '\\U+00E9', 'ê': '\\U+00EA',
            'í': '\\U+00ED',
            'ó': '\\U+00F3', 'ô': '\\U+00F4', 'õ': '\\U+00F5',
            'ú': '\\U+00FA',
            'ç': '\\U+00E7'
        }
        res = str(texto)
        for k, v in mapa.items():
            res = res.replace(k, v)
        return res

    def add_text(x, y, texto, height=2.0, color=7, layer="Tabela", rotation=0.0):
        texto_cad = sanitizar_dxf_unicode(texto)
        dxf.extend([
            "0", "TEXT",
            "8", layer,
            "62", str(color),
            "10", f"{x:.4f}", "20", f"{y:.4f}", "30", "0.0",
            "40", f"{height:.4f}",
            "1", texto_cad,
            "7", "STANDARD",
            "50", f"{rotation:.2f}"
        ])

    def add_multiline_text(x, y, texto, height=2.0, color=7, layer="Tabela", rotation=0.0):
        linhas = str(texto).split(" - ")
        rad = math.radians(rotation + 90)
        
        espacamento = height * 1.4
        offset_x = math.cos(rad) * espacamento
        offset_y = math.sin(rad) * espacamento

        for idx, lin in enumerate(linhas):
            px = x - (idx * offset_x)
            py = y - (idx * offset_y)
            add_text(px, py, lin.strip(), height=height, color=color, layer=layer, rotation=rotation)

    # TEXTO DA ÁREA CENTRALIZADO
    if centroide:
        add_text(centroide.x(), centroide.y(), f"ÁREA: {area_txt} m²", height=(2.5 * fator_escala), color=1, layer="_TEXTO_CENTRAL")

    # DESENHO DA TABELA
    add_line(tab_x + c0, tab_y, tab_x + c6, tab_y)
    add_line(tab_x + c0, tab_y - h6, tab_x + c6, tab_y - h6)
    add_line(tab_x + c0, tab_y - h12, tab_x + c6, tab_y - h12)
    add_line(tab_x + c0, tab_y - h18, tab_x + c6, tab_y - h18)

    add_text(tab_x + (4 * fator_escala), tab_y - h6 + h2, "TABELA DE AZIMUTES, DISTÂNCIAS E COORDENADAS", txt_tam_titulo)
    add_text(tab_x + (3 * fator_escala), tab_y - h12 + h2, "LADOS", txt_tam_dados)
    add_text(tab_x + c2 + (2 * fator_escala), tab_y - h12 + h2, "AZIMUTE (UTM)", txt_tam_dados)
    add_text(tab_x + c3 + (1.0 * fator_escala), tab_y - h12 + h2, "DISTÂNCIA (UTM)", txt_tam_dados)
    add_text(tab_x + c4 + (4 * fator_escala), tab_y - h12 + h2, "COORDENADAS UTM", txt_tam_dados)
    
    add_text(tab_x + (2 * fator_escala), tab_y - h18 + h2, "De", txt_tam_dados)
    add_text(tab_x + c1 + (2 * fator_escala), tab_y - h18 + h2, "Para", txt_tam_dados)
    add_text(tab_x + c2 + (3 * fator_escala), tab_y - h18 + h2, "g - m - s", txt_tam_dados)
    add_text(tab_x + c3 + (4 * fator_escala), tab_y - h18 + h2, "metros", txt_tam_dados)
    add_text(tab_x + c4 + (2 * fator_escala), tab_y - h18 + h2, "E (metros)", txt_tam_dados)
    add_text(tab_x + c5 + (2 * fator_escala), tab_y - h18 + h2, "N (metros)", txt_tam_dados)

    add_line(tab_x + c0, tab_y, tab_x + c0, tab_y - h18) 
    add_line(tab_x + c1, tab_y - h12, tab_x + c1, tab_y - h18) 
    add_line(tab_x + c2, tab_y - h6, tab_x + c2, tab_y - h18) 
    add_line(tab_x + c3, tab_y - h6, tab_x + c3, tab_y - h18) 
    add_line(tab_x + c4, tab_y - h6, tab_x + c4, tab_y - h18) 
    add_line(tab_x + c5, tab_y - h12, tab_x + c5, tab_y - h18) 
    add_line(tab_x + c6, tab_y, tab_x + c6, tab_y - h18) 

    y_acumulado = tab_y - h18
    for d in dados_tabela:
        y_acumulado -= h6
        add_text(tab_x + c0 + pad_esquerd0, y_acumulado + h2, d['de'], txt_tam_dados)
        add_text(tab_x + c1 + pad_esquerd0, y_acumulado + h2, d['para'], txt_tam_dados)
        add_text(tab_x + c2 + pad_esquerd0, y_acumulado + h2, d['az'], txt_tam_dados)
        add_text(tab_x + c3 + pad_esquerd0, y_acumulado + h2, d['dist'], txt_tam_dados)
        add_text(tab_x + c4 + pad_esquerd0, y_acumulado + h2, d['e'], txt_tam_dados)
        add_text(tab_x + c5 + pad_esquerd0, y_acumulado + h2, d['n'], txt_tam_dados)
        
        add_line(tab_x + c0, y_acumulado + h6, tab_x + c0, y_acumulado)
        add_line(tab_x + c1, y_acumulado + h6, tab_x + c1, y_acumulado)
        add_line(tab_x + c2, y_acumulado + h6, tab_x + c2, y_acumulado)
        add_line(tab_x + c3, y_acumulado + h6, tab_x + c3, y_acumulado)
        add_line(tab_x + c4, y_acumulado + h6, tab_x + c4, y_acumulado)
        add_line(tab_x + c5, y_acumulado + h6, tab_x + c5, y_acumulado)
        add_line(tab_x + c6, y_acumulado + h6, tab_x + c6, y_acumulado)

    add_line(tab_x + c0, y_acumulado, tab_x + c6, y_acumulado)

    # POLIGONAL E CONFRONTANTES
    for i in range(len(nodes) - 1):
        p_idx1 = nodes[i]
        p_idx2 = nodes[i+1]
        add_line(p_idx1.x(), p_idx1.y(), p_idx2.x(), p_idx2.y(), layer="_POLIGONAL")
        
        if i < len(confrontantes):
            conf_txt = confrontantes[i]
            if conf_txt and conf_txt != "NÃO INFORMADO":
                mx = (p_idx1.x() + p_idx2.x()) / 2.0
                my = (p_idx1.y() + p_idx2.y()) / 2.0
                dx = p_idx2.x() - p_idx1.x()
                dy = p_idx2.y() - p_idx1.y()
                angulo_graus = math.degrees(math.atan2(dy, dx))
                
                if angulo_graus > 90 or angulo_graus < -90:
                    angulo_graus += 180.0
                    
                dist_linha = math.hypot(dx, dy)
                if dist_linha > 0:
                    nx = -dy / dist_linha
                    ny = dx / dist_linha
                    mx += nx * (2.5 * fator_escala)
                    my += ny * (2.5 * fator_escala)
                    
                add_multiline_text(mx, my, conf_txt, height=(1.3 * fator_escala), color=8, layer="_CONFRONTANTES", rotation=angulo_graus)

    # VÉRTICES (CÍRCULOS E TEXTO)
    escala_ponto = fator_escala * 0.8
    if escala_ponto < 0.2: escala_ponto = 0.2
    if escala_ponto > 10.0: escala_ponto = 10.0

    pontos_mapa = nodes[:-1] if nodes[0] == nodes[-1] else nodes
    for i, p in enumerate(pontos_mapa):
        nome_vertice = dados_tabela[i]['de'] if i < len(dados_tabela) else f"P{i+1}"
        
        dxf.extend([
            "0", "CIRCLE",
            "8", "_PONTOS_DO_PROJETO",
            "62", "1",
            "10", f"{p.x():.4f}", "20", f"{p.y():.4f}", "30", "0.0",
            "40", f"{(0.4 * escala_ponto):.4f}"
        ])
        
        add_text(p.x() + (0.6 * escala_ponto), p.y() + (0.6 * escala_ponto), nome_vertice, height=(1.2 * escala_ponto), color=7, layer="_PONTOS_DO_PROJETO")

    dxf.extend(["0", "ENDSEC", "0", "EOF"])

    with open(caminho_arquivo, 'w', encoding='utf-8') as f:
        f.write("\n".join(dxf))


# --- FUNÇÃO GERENCIADORA DA CAMADA DE VÉRTICES NATIVA NO QGIS ---
def criar_camada_vertices_qgis(pontos, nomes):
    remover_camada_vertices_qgis()
    layer_mem = QgsVectorLayer("Point?crs=" + QgsProject.instance().crs().authid() + "&field=nome:string(20)", "Vértices do Memorial (Temporário)", "memory")
    pr = layer_mem.dataProvider()
    
    features = []
    for p, nome in zip(pontos, nomes):
        fet = QgsFeature()
        fet.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(p.x(), p.y())))
        fet.setAttributes([nome])
        features.append(fet)
        
    pr.addFeatures(features)
    layer_mem.updateFields()
    
    text_format = QgsTextFormat()
    text_format.setSize(11)
    text_format.setColor(QColor(255, 0, 0))
    
    fnt = text_format.font()
    fnt.setBold(True)
    text_format.setFont(fnt)
    
    lbl_settings = QgsPalLayerSettings()
    lbl_settings.fieldName = "nome"
    lbl_settings.setFormat(text_format)
    lbl_settings.placement = Qgis.LabelPlacement.OrderedPositionsAroundPoint
    lbl_settings.distance = 3.0
    
    labels = QgsVectorLayerSimpleLabeling(lbl_settings)
    layer_mem.setLabeling(labels)
    layer_mem.setLabelsEnabled(True)
    
    QgsProject.instance().addMapLayer(layer_mem)
    iface.mapCanvas().refresh()
    return layer_mem

def remover_camada_vertices_qgis():
    layers = QgsProject.instance().mapLayersByName("Vértices do Memorial (Temporário)")
    if layers:
        for layer_item in layers:
            QgsProject.instance().removeMapLayer(layer_item)
    iface.mapCanvas().refresh()


# --- INTERFACE DE VÉRTICES INTERATIVOS ---
class EdicaoVerticesDialog(QDialog):
    def __init__(self, pontos):
        super().__init__(iface.mainWindow())
        self.setWindowTitle("Configurar Nomes dos Vértices")
        self.setMinimumWidth(550)
        self.layout = QVBoxLayout()
        
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("<b>Iniciar sequência no número:</b>"))
        self.spin_inicio = QSpinBox()
        self.spin_inicio.setRange(1, 99999)
        self.spin_inicio.setValue(1)  
        self.spin_inicio.setFixedWidth(80)
        self.spin_inicio.valueChanged.connect(self.reindexar_nomes_padrao)
        ctrl_layout.addWidget(self.spin_inicio)
        ctrl_layout.addStretch()
        self.layout.addLayout(ctrl_layout)
        
        self.layout.addWidget(QLabel("Selecione um vértice para localizá-lo no mapa. Altere individualmente se necessário:"))
        
        self.table = QTableWidget(len(pontos), 3)
        self.table.setHorizontalHeaderLabels(["Nome do Vértice", "Coord E", "Coord N"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        self.pontos = pontos
        self.canvas = iface.mapCanvas()
        self.nomes_finais = []
        
        self.table.blockSignals(True)
        for row, p in enumerate(pontos):
            chave = f"{p.x():.3f}|{p.y():.3f}"
            nome_sugerido = MEMORIA_COORDENADAS.get(chave, f"P{row+1}")
            
            item_nome = QTableWidgetItem(nome_sugerido)
            if chave in MEMORIA_COORDENADAS:
                item_nome.setBackground(QColor(200, 255, 200)) 
                
            self.table.setItem(row, 0, item_nome)
            
            item_e = QTableWidgetItem(formata_coordenada(p.x(), 3))
            item_e.setFlags(item_e.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, item_e)
            
            item_n = QTableWidgetItem(formata_coordenada(p.y(), 3))
            item_n.setFlags(item_n.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, item_n)
            
        self.table.blockSignals(False)
        self.layout.addWidget(self.table)
        
        self.atualizar_camada_em_tela()
        
        self.btn_ok = QPushButton("Confirmar Vértices")
        self.btn_ok.clicked.connect(self.salvar_e_fechar)
        self.layout.addWidget(self.btn_ok)
        self.setLayout(self.layout)
        
        self.table.cellChanged.connect(self.on_cell_changed)
        
    def pegar_nomes_da_tabela(self):
        nomes = []
        for r in range(self.table.rowCount()):
            txt = self.table.item(r, 0).text().strip()
            nomes.append(txt if txt else f"P{r+1}")
        return nomes

    def atualizar_camada_em_tela(self):
        nomes = self.pegar_nomes_da_tabela()
        criar_camada_vertices_qgis(self.pontos, nomes)

    def on_cell_changed(self, row, col):
        if col == 0:
            self.atualizar_camada_em_tela()

    def reindexar_nomes_padrao(self):
        self.table.blockSignals(True)
        inicio = self.spin_inicio.value()
        for row in range(self.table.rowCount()):
            p = self.pontos[row]
            chave = f"{p.x():.3f}|{p.y():.3f}"
            if chave not in MEMORIA_COORDENADAS:
                self.table.item(row, 0).setText(f"P{inicio + row}")
        self.table.blockSignals(False)
        self.atualizar_camada_em_tela()

    def salvar_e_fechar(self):
        self.nomes_finais = self.pegar_nomes_da_tabela()
        for row, nome in enumerate(self.nomes_finais):
            p = self.pontos[row]
            chave = f"{p.x():.3f}|{p.y():.3f}"
            MEMORIA_COORDENADAS[chave] = nome
        self.accept()
        
    def reject(self):
        remover_camada_vertices_qgis()
        super().reject()


# --- JANELA DE CONFRONTANTES ---
class SeletorConfrontanteTool(QgsMapToolIdentifyFeature):
    feature_identificada = pyqtSignal(object)
    def __init__(self, canvas, layer=None):
        super().__init__(canvas)
        self.canvas = canvas
        if layer: self.setLayer(layer)
    def canvasReleaseEvent(self, event):
        resultados = self.identify(event.x(), event.y(), self.TopDownStopAtFirst)
        if resultados: self.feature_identificada.emit(resultados[0].mFeature)


class MemorialDialog(QDialog):
    def __init__(self, trecho_info, p_atual, p_prox, canvas):
        super().__init__(iface.mainWindow())
        self.setWindowTitle(f"Confrontante: {p_atual} -> {p_prox}")
        self.canvas = canvas
        self.trecho_info = trecho_info
        
        self.layout = QVBoxLayout()
        self.layout.addWidget(QLabel(f"<b>Trecho:</b> {p_atual} para {p_prox}"))
        self.layout.addWidget(QLabel(self.trecho_info))
        self.layout.addWidget(QLabel("<hr>"))
        self.layout.addWidget(QLabel("Texto do Confrontante (Lote, Matrícula, Proprietário):"))
        
        self.confrontante_edit = QLineEdit()
        self.confrontante_edit.setMinimumWidth(350) 
        self.layout.addWidget(self.confrontante_edit)
        
        btn_layout = QHBoxLayout()
        self.btn_mapa = QPushButton("📍 Selecionar no Mapa")
        self.btn_mapa.setAutoDefault(False)
        self.btn_mapa.clicked.connect(self.activar_ferramenta_mapa)
        
        self.btn_salvar = QPushButton("Salvar e Próximo")
        self.btn_salvar.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_mapa)
        btn_layout.addWidget(self.btn_salvar)
        self.layout.addLayout(btn_layout)
        self.setLayout(self.layout)
        self.tool = None

    def activar_ferramenta_mapa(self):
        self.hide()
        iface.mainWindow().activateWindow()
        iface.messageBar().pushMessage("Ação", "Clique no texto ou lote no mapa. (Aperte ESC para voltar)", level=0, duration=5)
        self.tool = SeletorConfrontanteTool(self.canvas)
        self.canvas.setMapTool(self.tool)
        self.loop_mapa = QEventLoop()
        self.tool.feature_identificada.connect(self.preencher_campos)
        self.tool.deactivated.connect(self.cancelar_mapa)
        self.loop_mapa.exec()

    def preencher_campos(self, feature):
        try:
            self.tool.deactivated.disconnect(self.cancelar_mapa)
        except (TypeError, Exception):  # nosec
            _ = None

        valores_encontrados = []
        for valor in feature.attributes():
            str_val = str(valor).strip()
            if str_val and str_val.upper() != 'NULL':
                valores_encontrados.append(str_val)
        self.confrontante_edit.setText(" - ".join(valores_encontrados))
        self.canvas.unsetMapTool(self.tool)
        self.show()
        if self.loop_mapa.isRunning():
            self.loop_mapa.quit()

    def cancelar_mapa(self):
        self.canvas.unsetMapTool(self.tool)
        self.show()
        if self.loop_mapa.isRunning(): self.loop_mapa.quit()


# --- MENU DE EXPORTAÇÃO ---
class MenuExportacaoDialog(QDialog):
    def __init__(self):
        super().__init__(iface.mainWindow())
        self.setWindowTitle("Exportação de Documentos de Topografia")
        self.setMinimumWidth(430)
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("<b>Dados processados em alta precisão!</b> Escolha a precisão desejada:"))
        
        grp_precision = QGroupBox("Casas Decimais (Arredondamento de Saída)")
        form_layout = QFormLayout()
        
        self.spin_dist = QSpinBox()
        self.spin_dist.setRange(1, 4)
        self.spin_dist.setValue(2)
        
        self.spin_coord = QSpinBox()
        self.spin_coord.setRange(1, 4)
        self.spin_coord.setValue(3)
        
        self.spin_az_sec = QSpinBox()
        self.spin_az_sec.setRange(0, 3)
        self.spin_az_sec.setValue(0)
        
        form_layout.addRow("Distâncias (metros):", self.spin_dist)
        form_layout.addRow("Coordenadas N/E (metros):", self.spin_coord)
        form_layout.addRow("Azimutes (casas nos segundos):", self.spin_az_sec)
        grp_precision.setLayout(form_layout)
        layout.addWidget(grp_precision)
        
        layout.addWidget(QLabel("<small>O arredondamento será applied somente na geração do arquivo.</small>"))
        layout.addWidget(QLabel("<hr>"))
        
        self.btn_word = QPushButton("📝 Gerar Memorial Descritivo (Word)")
        self.btn_word.setMinimumHeight(40)
        self.btn_word.clicked.connect(self.exportar_word)
        layout.addWidget(self.btn_word)
        
        self.btn_dxf = QPushButton("📐 Gerar Planta e Tabela (DXF)")
        self.btn_dxf.setMinimumHeight(40)
        self.btn_dxf.clicked.connect(self.exportar_dxf)
        layout.addWidget(self.btn_dxf)
        
        layout.addWidget(QLabel("<hr>"))
        self.btn_sair = QPushButton("Fechar Painel")
        self.btn_sair.clicked.connect(self.accept)
        layout.addWidget(self.btn_sair)
        self.setLayout(layout)

    def obter_dados_formatados(self):
        raw_data = DADOS_ULTIMO_PROCESSAMENTO["raw_data"]
        reordered = DADOS_ULTIMO_PROCESSAMENTO["reordered"]
        confrontantes = DADOS_ULTIMO_PROCESSAMENTO["lista_confrontantes"]
        area_real = DADOS_ULTIMO_PROCESSAMENTO["area_real"]
        
        c_dist = self.spin_dist.value()
        c_coord = self.spin_coord.value()
        c_az_sec = self.spin_az_sec.value()
        
        area_txt = formata_area(area_real)
        
        n_ini = formata_coordenada(reordered[0].y(), c_coord)
        e_ini = formata_coordenada(reordered[0].x(), c_coord)
        nome_ini = raw_data[0]['de']
        
        texto_html = "<html><body>"
        texto_html += f"<p style='font-family: Arial; font-size: 11pt; font-weight: bold;'>ÁREA: {area_txt} m²</p>"
        texto_html += "<p style='text-align: justify; font-family: Arial; font-size: 11pt; margin-top: 12px;'>"
        texto_html += f"Inicia-se a descrição deste perímetro no vértice <b>{nome_ini}</b>, de coordenadas N <b>{n_ini} m</b> e E <b>{e_ini} m</b>; "
        
        dados_tabela_formatados = []
        
        for item in raw_data:
            az_fmt = formata_azimute(item['az_dec'], c_az_sec)
            dist_fmt = formata_distancia(item['dist_raw'], c_dist)
            n_fmt = formata_coordenada(item['p_prox'].y(), c_coord)
            e_fmt = formata_coordenada(item['p_prox'].x(), c_coord)
            
            dados_tabela_formatados.append({
                'de': item['de'],
                'para': item['para'],
                'az': az_fmt,
                'dist': dist_fmt,
                'e': e_fmt,
                'n': n_fmt
            })
            
            conf_txt = item['confrontante']
            texto_html += (f"deste, segue com azimute de <b>{az_fmt}</b> e distância de <b>{dist_fmt} m</b>, "
                            f"confrontando neste trecho com <b>{conf_txt}</b>, até o vértice <b>{item['para']}</b>, "
                            f"de coordenadas N <b>{n_fmt} m</b> e E <b>{e_fmt} m</b>; ")
            
        texto_html += f"ponto inicial da descrição deste perímetro. Todas as coordenadas aqui descritas estão geo-referenciadas ao Sistema Geodésico Brasileiro Sirgas 2000. Todos os azimutes e distâncias, áreas e perímetros foram calculados no plano de projeção UTM. Obs.: Não consta área de APP. Totalizando uma área descrita de <b>{area_txt} m²</b>.</p></body></html>"
        
        return texto_html, dados_tabela_formatados, area_txt

    def exportar_word(self):
        texto_html, _, _ = self.obter_dados_formatados()
        while True:
            caminho_doc, _ = QFileDialog.getSaveFileName(iface.mainWindow(), "Salvar Memorial Descritivo (Word)", "", "Word Document (*.doc)")
            if not caminho_doc: return
            if not caminho_doc.endswith('.doc'): caminho_doc += '.doc'
            try:
                with open(caminho_doc, 'w', encoding='utf-8') as f:
                    f.write(texto_html)
                QMessageBox.information(iface.mainWindow(), "Sucesso", "Memorial Word gerado com sucesso!")
                break
            except PermissionError:
                QMessageBox.critical(iface.mainWindow(), "Erro de Permissão", "O arquivo está aberto no Word! Feche-o e tente novamente.")
            except Exception as e:
                QMessageBox.critical(iface.mainWindow(), "Erro", str(e))
                break

    def exportar_dxf(self):
        _, dados_tabela_fmt, area_txt = self.obter_dados_formatados()
        while True:
            caminho_salvar, _ = QFileDialog.getSaveFileName(iface.mainWindow(), "Salvar Tabela DXF", "", "DXF Files (*.dxf)")
            if not caminho_salvar: return
            if not caminho_salvar.endswith('.dxf'): caminho_salvar += '.dxf'
            try:
                gerar_tabela_e_desenho_dxf(
                    dados_tabela_fmt, 
                    DADOS_ULTIMO_PROCESSAMENTO["reordered"], 
                    DADOS_ULTIMO_PROCESSAMENTO["lista_confrontantes"], 
                    area_txt,
                    DADOS_ULTIMO_PROCESSAMENTO["centroide"],
                    caminho_salvar
                )
                QMessageBox.information(iface.mainWindow(), "Sucesso", "Desenho e Tabela DXF salvos com sucesso!")
                break
            except PermissionError:
                QMessageBox.critical(iface.mainWindow(), "Erro de Permissão", "O arquivo está aberto no AutoCAD! Feche-o e tente novamente.")
            except Exception as e:
                QMessageBox.critical(iface.mainWindow(), "Erro Crítico", str(e))
                break


# --- MOTOR PRINCIPAL ---
def gerar_memorial_interativo():
    layer = iface.activeLayer()
    if not layer or not isinstance(layer, QgsVectorLayer): return

    selecao = layer.selectedFeatures()
    if not selecao:
        QMessageBox.warning(iface.mainWindow(), "Aviso", "Selecione a linha ou polígono do imóvel primeiro!")
        return

    feat = selecao[0]
    geom = feat.geometry()
    
    geom_type = geom.type()
    raw_nodes = []

    if geom_type == Qgis.GeometryType.PolygonGeometry:
        raw_nodes = geom.asMultiPolygon()[0][0] if geom.isMultipart() else geom.asPolygon()[0]
    elif geom_type == Qgis.GeometryType.LineGeometry:
        raw_nodes = geom.asMultiPolyline()[0] if geom.isMultipart() else geom.asPolyline()
    else: return

    nodes = []
    for p in raw_nodes:
        duplicado = False
        for salvo in nodes:
            if math.isclose(p.x(), salvo.x(), abs_tol=0.001) and math.isclose(p.y(), salvo.y(), abs_tol=0.001):
                duplicado = True
                break
        if not duplicado: nodes.append(p)

    temp_nodes = nodes + [nodes[0]]
    soma_area = 0
    for i in range(len(temp_nodes) - 1):
        soma_area += (temp_nodes[i+1].x() - temp_nodes[i].x()) * (temp_nodes[i+1].y() + temp_nodes[i].y())
    
    if soma_area < 0: 
        nodes = nodes[::-1]
        soma_area = abs(soma_area)

    area_real = soma_area / 2.0

    cx = sum(p.x() for p in nodes) / float(len(nodes))
    cy = sum(p.y() for p in nodes) / float(len(nodes))
    centroide_geom = QgsPointXY(cx, cy)

    sorted_nodes = sorted(enumerate(nodes), key=lambda x: (-x[1].y(), x[1].x()))
    p1_index = sorted_nodes[0][0]
    reordered = nodes[p1_index:] + nodes[:p1_index]
    reordered.append(reordered[0])

    canvas = iface.mapCanvas()
    pontos_unicos = reordered[:-1]
    dialog_vertices = EdicaoVerticesDialog(pontos_unicos)
    dialog_vertices.exec()
    
    if dialog_vertices.result() != QDialog.DialogCode.Accepted:
        remover_camada_vertices_qgis()
        return
        
    nomes_vertices = dialog_vertices.nomes_finais
    nomes_vertices.append(nomes_vertices[0]) 

    raw_data = [] 
    lista_confrontantes = [] 
    sucesso_completo = False

    try:
        criar_camada_vertices_qgis(pontos_unicos, dialog_vertices.nomes_finais)

        for i in range(len(reordered) - 1):
            nome_atual = nomes_vertices[i]
            nome_prox = nomes_vertices[i+1]
            p_atual = reordered[i]
            p_prox = reordered[i+1]
            
            dist_raw = p_atual.distance(p_prox)
            az_dec = p_atual.azimuth(p_prox)
            if az_dec < 0: az_dec += 360
            
            info_trecho = f"Azimute: {formata_azimute(az_dec)} | Distância: {formata_distancia(dist_raw)} m"
            
            linha_destaque = QgsRubberBand(canvas, Qgis.GeometryType.LineGeometry)
            linha_destaque.setColor(QColor(0, 255, 0)) 
            linha_destaque.setWidth(4)
            linha_destaque.addPoint(p_atual)
            linha_destaque.addPoint(p_prox)
            linha_destaque.show()

            dialog = MemorialDialog(info_trecho, nome_atual, nome_prox, canvas)
            dialog.setModal(False)
            dialog.show()
            
            loop_principal = QEventLoop()
            dialog.accepted.connect(loop_principal.quit)
            dialog.rejected.connect(loop_principal.quit)
            loop_principal.exec()
            
            resultado = dialog.result()
            linha_destaque.reset()
            
            if resultado == QDialog.DialogCode.Accepted:
                confrontante_txt = dialog.confrontante_edit.text()
                if not confrontante_txt.strip(): confrontante_txt = "NÃO INFORMADO"
                
                lista_confrontantes.append(confrontante_txt)
                
                raw_data.append({
                    'de': nome_atual,
                    'para': nome_prox,
                    'p_atual': p_atual,
                    'p_prox': p_prox,
                    'dist_raw': dist_raw,
                    'az_dec': az_dec,
                    'confrontante': confrontante_txt
                })
            else: return

        sucesso_completo = True

    finally:
        remover_camada_vertices_qgis()

    if sucesso_completo:
        DADOS_ULTIMO_PROCESSAMENTO["raw_data"] = raw_data
        DADOS_ULTIMO_PROCESSAMENTO["reordered"] = reordered
        DADOS_ULTIMO_PROCESSAMENTO["lista_confrontantes"] = lista_confrontantes
        DADOS_ULTIMO_PROCESSAMENTO["area_real"] = area_real
        DADOS_ULTIMO_PROCESSAMENTO["centroide"] = centroide_geom
        
        menu = MenuExportacaoDialog()
        menu.exec()

if __name__ == '__main__':
    gerar_memorial_interativo()