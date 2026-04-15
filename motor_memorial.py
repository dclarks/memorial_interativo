import math
import os
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QFileDialog
from qgis.PyQt.QtCore import Qt, pyqtSignal, QEventLoop, QVariant
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsMapToolIdentifyFeature, QgsRubberBand
from qgis.core import QgsProject, QgsField, QgsGeometry, QgsVectorLayer, QgsWkbTypes
from qgis.utils import iface

# --- FUNÇÕES AUXILIARES ---
def formata_br(valor, casas=2):
    """Transforma 1234.56 em 1.234,56"""
    texto_us = f"{valor:,.{casas}f}"
    return texto_us.replace(",", "X").replace(".", ",").replace("X", ".")

def verificar_sentido_horario(pontos):
    """Utiliza a fórmula de Shoelace para verificar se os pontos estão em sentido horário"""
    soma = 0
    for i in range(len(pontos)):
        p1 = pontos[i]
        p2 = pontos[(i + 1) % len(pontos)]
        soma += (p2.x() - p1.x()) * (p2.y() + p1.y())
    return soma > 0  # Retorna True se for Horário

def gerar_tabela_dxf(dados, caminho_arquivo):
    """Gera um arquivo DXF com a tabela de coordenadas e fonte Romans"""
    
    # Adicionando o cabeçalho de estilos para carregar a fonte Romans.shx no AutoCAD
    dxf = [
        "0", "SECTION", "2", "TABLES",
        "0", "TABLE", "2", "STYLE", "70", "1",
        "0", "STYLE", "2", "ROMANS", "70", "0", "40", "0.0", "41", "1.0", "50", "0.0", "71", "0", "42", "0.2", "3", "romans.shx", "4", "",
        "0", "ENDTAB",
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES"
    ]

    def add_line(x1, y1, x2, y2):
        dxf.extend(["0", "LINE", "8", "Tabela", "10", str(x1), "20", str(y1), "11", str(x2), "21", str(y2)])

    def add_text(x, y, texto, height=2.0):
        texto_cad = texto.replace("°", "%%d")
        # O código '7', 'ROMANS' força o AutoCAD a usar o estilo criado acima
        dxf.extend(["0", "TEXT", "8", "Tabela", "10", str(x), "20", str(y), "40", str(height), "7", "ROMANS", "1", texto_cad])

    # Cabeçalho da Tabela
    add_line(0, 0, 170, 0)
    add_line(0, -6, 170, -6)
    add_line(0, -12, 170, -12)
    add_line(0, -18, 170, -18)

    add_text(25, -4, "TABELA DE AZIMUTES, DISTANCIAS E COORDENADAS", 2.5)
    add_text(10, -10, "LADOS")
    add_text(35, -10, "AZIMUTE (UTM)")
    add_text(68, -10, "DISTANCIA (UTM)")
    add_text(110, -10, "COORDENADAS UTM")
    
    add_text(2, -16, "Vertices")
    add_text(17, -16, "Vertices")
    add_text(73, -16, "metros")
    add_text(102, -16, "E metros")
    add_text(138, -16, "N metros")

    # Linhas Verticais Iniciais
    add_line(0, 0, 0, -18) 
    add_line(30, -6, 30, -18) 
    add_line(15, -12, 15, -18) 
    add_line(65, -6, 65, -18) 
    add_line(95, -6, 95, -18) 
    add_line(130, -12, 130, -18) 
    add_line(170, 0, 170, -18) 

    y = -18
    for d in dados:
        y -= 6
        add_text(2, y+2, d['de'])
        add_text(17, y+2, d['para'])
        add_text(35, y+2, d['az'])
        add_text(73, y+2, d['dist'])
        add_text(98, y+2, d['e'])
        add_text(133, y+2, d['n'])
        
        add_line(0, y+6, 0, y)
        add_line(15, y+6, 15, y)
        add_line(30, y+6, 30, y)
        add_line(65, y+6, 65, y)
        add_line(95, y+6, 95, y)
        add_line(130, y+6, 130, y)
        add_line(170, y+6, 170, y)

    add_line(0, y, 170, y)
    dxf.extend(["0", "ENDSEC", "0", "EOF"])

    with open(caminho_arquivo, 'w', encoding='utf-8') as f:
        f.write("\n".join(dxf))

class SeletorConfrontanteTool(QgsMapToolIdentifyFeature):
    feature_identificada = pyqtSignal(object)
    def __init__(self, canvas, layer=None):
        super().__init__(canvas)
        self.canvas = canvas
        if layer: self.setLayer(layer)
    def canvasReleaseEvent(self, event):
        resultados = self.identify(event.x(), event.y(), self.TopDownStopAtFirst)
        if resultados:
            self.feature_identificada.emit(resultados[0].mFeature)

class MemorialDialog(QDialog):
    def __init__(self, trecho_info, p_atual, p_prox, canvas):
        super().__init__(iface.mainWindow())
        self.setWindowTitle(f"Confrontante: {p_atual} -> {p_prox}")
        self.canvas = canvas
        self.trecho_info = trecho_info
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"<b>Trecho:</b> {p_atual} para {p_prox}"))
        layout.addWidget(QLabel(self.trecho_info))
        layout.addWidget(QLabel("<hr>"))
        layout.addWidget(QLabel("Texto do Confrontante (Lote, Matrícula, Proprietário):"))
        self.confrontante_edit = QLineEdit()
        self.confrontante_edit.setMinimumWidth(350) 
        layout.addWidget(self.confrontante_edit)
        btn_layout = QHBoxLayout()
        self.btn_mapa = QPushButton("📍 Selecionar no Mapa")
        self.btn_mapa.setAutoDefault(False)
        self.btn_mapa.clicked.connect(self.ativar_ferramenta_mapa)
        self.btn_salvar = QPushButton("Salvar e Próximo")
        self.btn_salvar.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_mapa)
        btn_layout.addWidget(self.btn_salvar)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.tool = None

    def ativar_ferramenta_mapa(self):
        self.hide()
        iface.mainWindow().activateWindow()
        self.tool = SeletorConfrontanteTool(self.canvas)
        self.canvas.setMapTool(self.tool)
        self.loop_mapa = QEventLoop()
        self.tool.feature_identificada.connect(self.preencher_campos)
        self.tool.deactivated.connect(self.cancelar_mapa)
        self.loop_mapa.exec_()

    def preencher_campos(self, feature):
        valores = [str(v).strip() for v in feature.attributes() if str(v).strip() and str(v).upper() != 'NULL']
        self.confrontante_edit.setText(" - ".join(valores))
        self.canvas.unsetMapTool(self.tool)
        self.show()
        if self.loop_mapa.isRunning(): self.loop_mapa.quit()

    def cancelar_mapa(self):
        self.canvas.unsetMapTool(self.tool)
        self.show()
        if self.loop_mapa.isRunning(): self.loop_mapa.quit()

def gerar_memorial_interativo():
    layer = iface.activeLayer()
    if not layer or not layer.selectedFeatures():
        QMessageBox.warning(iface.mainWindow(), "Aviso", "Selecione um polígono/linha primeiro!")
        return

    geom = layer.selectedFeatures()[0].geometry()
    nodes = []

    if geom.type() == QgsWkbTypes.PolygonGeometry:
        nodes = geom.asMultiPolygon()[0][0][:-1] if geom.isMultipart() else geom.asPolygon()[0][:-1]
    elif geom.type() == QgsWkbTypes.LineGeometry:
        nodes = geom.asMultiPolyline()[0] if geom.isMultipart() else geom.asPolyline()
        if nodes[0] == nodes[-1]: nodes = nodes[:-1]

    # --- CORREÇÃO DE SENTIDO HORÁRIO ---
    if not verificar_sentido_horario(nodes):
        nodes.reverse()

    # Define P1 como o ponto mais ao Norte (Maior Y)
    sorted_nodes = sorted(enumerate(nodes), key=lambda x: (-x[1].y(), x[1].x()))
    p1_idx = sorted_nodes[0][0]
    reordered = nodes[p1_idx:] + nodes[:p1_idx]
    reordered.append(reordered[0])

    canvas = iface.mapCanvas()
    n_ini, e_ini = formata_br(reordered[0].y()), formata_br(reordered[0].x())
    
    # --- NOVIDADE: Fundo contínuo (Justificado) e Fonte Calibri ---
    texto_html = f"<html><body style='font-family: Calibri; font-size: 11pt; line-height: 1.5;'>"
    texto_html += f"<p style='text-align: justify;'>Inicia-se a descrição deste perímetro no <b>vértice P1</b>, de coordenadas <b>N:</b> {n_ini} m. e <b>E:</b> {e_ini} m.; "
    
    dados_tabela = []
    for i in range(len(reordered) - 1):
        nome_at = f"P{i+1}"
        nome_pr = "P1" if i == len(reordered) - 2 else f"P{i+2}"
        p1, p2 = reordered[i], reordered[i+1]
        
        dist = p1.distance(p2)
        az_dec = p1.azimuth(p2)
        if az_dec < 0: az_dec += 360
        d, m, s = int(az_dec), int((az_dec - int(az_dec)) * 60), (az_dec - int(az_dec) - int((az_dec - int(az_dec)) * 60)/60) * 3600
        
        dist_f, n_f, e_f = formata_br(dist), formata_br(p2.y()), formata_br(p2.x())
        dados_tabela.append({'de': nome_at, 'para': nome_pr, 'az': f"{d}°{m:02d}'{s:02.0f}\"", 'dist': dist_f, 'e': e_f, 'n': n_f})
        
        rb = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        rb.setColor(QColor(255, 0, 0))
        rb.setWidth(4)
        rb.addPoint(p1); rb.addPoint(p2); rb.show()
        
        dialog = MemorialDialog(f"Azimute: {d}°{m:02d}'{s:02.0f}\" | Distância: {dist_f}m", nome_at, nome_pr, canvas)
        dialog.exec_()
        rb.reset()
        
        if dialog.result() == QDialog.Accepted:
            confr = dialog.confrontante_edit.text() or "NÃO INFORMADO"
            # --- NOVIDADE: Sem <br>, texto corrido com vírgulas ---
            texto_html += (f"deste, segue com azimute de {d}°{m:02d}'{s:02.0f}\" e distância de {dist_f} m., "
                           f"confrontando neste trecho com <b>{confr}</b>, "
                           f"até o <b>vértice {nome_pr}</b>, de coordenadas "
                           f"<b>N:</b> {n_f} m. e <b>E:</b> {e_f} m.; ")
        else: return

    texto_html += "ponto inicial da descrição deste perímetro. Todas as coordenadas aqui descritas estão geo-referenciadas ao Sistema Geodésico Brasileiro Sirgas 2000. Todos os azimutes e distâncias, áreas e perímetros foram calculados no plano de projeção UTM. Obs.: Não consta área de APP.</p></body></html>"

    # Salvar Arquivos
    path_doc, _ = QFileDialog.getSaveFileName(iface.mainWindow(), "Salvar Memorial (Word)", "", "Word Document (*.doc)")
    if path_doc:
        if not path_doc.endswith('.doc'): path_doc += '.doc'
        with open(path_doc, 'w', encoding='utf-8') as f: f.write(texto_html)

    if QMessageBox.question(iface.mainWindow(), "DXF", "Gerar Tabela DXF?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
        path_dxf, _ = QFileDialog.getSaveFileName(iface.mainWindow(), "Salvar Tabela DXF", "", "DXF Files (*.dxf)")
        if path_dxf:
            if not path_dxf.endswith('.dxf'): path_dxf += '.dxf'
            gerar_tabela_dxf(dados_tabela, path_dxf)
            QMessageBox.information(iface.mainWindow(), "Sucesso", "Arquivos gerados!")
