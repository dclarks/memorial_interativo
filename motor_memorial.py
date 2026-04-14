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

def gerar_tabela_dxf(dados, caminho_arquivo):
    """Gera um arquivo DXF puro com a tabela de coordenadas"""
    dxf = ["0", "SECTION", "2", "ENTITIES"]

    def add_line(x1, y1, x2, y2):
        dxf.extend(["0", "LINE", "8", "Tabela", "10", str(x1), "20", str(y1), "11", str(x2), "21", str(y2)])

    def add_text(x, y, texto, height=2.0):
        texto_cad = texto.replace("°", "%%d")
        dxf.extend(["0", "TEXT", "8", "Tabela", "10", str(x), "20", str(y), "40", str(height), "1", texto_cad])

    # Desenhar Linhas Horizontais do Cabeçalho
    add_line(0, 0, 170, 0)
    add_line(0, -6, 170, -6)
    add_line(0, -12, 170, -12)
    add_line(0, -18, 170, -18)

    # Textos do Cabeçalho
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

    # Desenhar Linhas Verticais
    add_line(0, 0, 0, -18) 
    add_line(30, -6, 30, -18) 
    add_line(15, -12, 15, -18) 
    add_line(65, -6, 65, -18) 
    add_line(95, -6, 95, -18) 
    add_line(130, -12, 130, -18) 
    add_line(170, 0, 170, -18) 

    y = -18
    # Preencher os Dados
    for d in dados:
        y -= 6
        add_text(2, y+2, d['de'])
        add_text(17, y+2, d['para'])
        add_text(35, y+2, d['az'])
        add_text(73, y+2, d['dist'])
        add_text(98, y+2, d['e'])
        add_text(133, y+2, d['n'])
        
        # Prolongar linhas verticais para a nova linha
        add_line(0, y+6, 0, y)
        add_line(15, y+6, 15, y)
        add_line(30, y+6, 30, y)
        add_line(65, y+6, 65, y)
        add_line(95, y+6, 95, y)
        add_line(130, y+6, 130, y)
        add_line(170, y+6, 170, y)

    # Linha final de fechamento da tabela
    add_line(0, y, 170, y)
    dxf.extend(["0", "ENDSEC", "0", "EOF"])

    with open(caminho_arquivo, 'w', encoding='utf-8') as f:
        f.write("\n".join(dxf))


class SeletorConfrontanteTool(QgsMapToolIdentifyFeature):
    feature_identificada = pyqtSignal(object)

    def __init__(self, canvas, layer=None):
        super().__init__(canvas)
        self.canvas = canvas
        if layer:
            self.setLayer(layer)

    def canvasReleaseEvent(self, event):
        resultados = self.identify(event.x(), event.y(), self.TopDownStopAtFirst)
        if resultados:
            feat = resultados[0].mFeature
            self.feature_identificada.emit(feat)

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
        self.btn_mapa.clicked.connect(self.ativar_ferramenta_mapa)
        
        self.btn_salvar = QPushButton("Salvar e Próximo")
        self.btn_salvar.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_mapa)
        btn_layout.addWidget(self.btn_salvar)
        self.layout.addLayout(btn_layout)
        
        self.setLayout(self.layout)
        self.tool = None

    def ativar_ferramenta_mapa(self):
        self.hide()
        iface.mainWindow().activateWindow()
        iface.messageBar().pushMessage("Ação", "Clique no texto ou lote no mapa. (Aperte ESC para voltar)", level=0, duration=5)
        
        self.tool = SeletorConfrontanteTool(self.canvas)
        self.canvas.setMapTool(self.tool)
        
        self.loop_mapa = QEventLoop()
        self.tool.feature_identificada.connect(self.preencher_campos)
        self.tool.deactivated.connect(self.cancelar_mapa)
        
        self.loop_mapa.exec_()

    def preencher_campos(self, feature):
        try:
            self.tool.deactivated.disconnect(self.cancelar_mapa)
        except:
            pass

        valores_encontrados = []
        for valor in feature.attributes():
            str_val = str(valor).strip()
            if str_val and str_val.upper() != 'NULL':
                valores_encontrados.append(str_val)
        
        texto_final_ponto = " - ".join(valores_encontrados)
        self.confrontante_edit.setText(texto_final_ponto)
                
        self.canvas.unsetMapTool(self.tool)
        self.show()
        if self.loop_mapa.isRunning():
            self.loop_mapa.quit()

    def cancelar_mapa(self):
        self.canvas.unsetMapTool(self.tool)
        self.show()
        if self.loop_mapa.isRunning():
            self.loop_mapa.quit()


def gerar_memorial_interativo():
    layer = iface.activeLayer()
    if not layer:
        return

    if not isinstance(layer, QgsVectorLayer):
        QMessageBox.warning(iface.mainWindow(), "Aviso", "Selecione a camada do desenho (Vetor), não uma imagem!")
        return

    selecao = layer.selectedFeatures()
    if not selecao:
        QMessageBox.warning(iface.mainWindow(), "Aviso", "Selecione a linha ou polígono do imóvel primeiro!")
        return

    feat = selecao[0]
    geom = feat.geometry()
    
    geom_type = geom.type()
    nodes = []

    if geom_type == QgsWkbTypes.PolygonGeometry:
        if geom.isMultipart():
            nodes = geom.asMultiPolygon()[0][0][:-1]
        else:
            nodes = geom.asPolygon()[0][:-1]
    elif geom_type == QgsWkbTypes.LineGeometry:
        if geom.isMultipart():
            nodes = geom.asMultiPolyline()[0]
        else:
            nodes = geom.asPolyline()
        if nodes and (nodes[0] == nodes[-1]):
            nodes = nodes[:-1]
    else:
        QMessageBox.warning(iface.mainWindow(), "Aviso", "Geometria não suportada! Precisa ser Linha ou Polígono.")
        return

    sorted_nodes = sorted(enumerate(nodes), key=lambda x: (-x[1].y(), x[1].x()))
    p1_index = sorted_nodes[0][0]

    reordered = nodes[p1_index:] + nodes[:p1_index]
    reordered.append(reordered[0])

    if layer.fields().indexFromName('Memorial') == -1:
        layer.startEditing()
        layer.dataProvider().addAttributes([QgsField('Memorial', QVariant.String)])
        layer.updateFields()
        layer.commitChanges()

    canvas = iface.mapCanvas()
    n_inicial = formata_br(reordered[0].y())
    e_inicial = formata_br(reordered[0].x())
    texto_final = f"Inicia-se a descrição deste perímetro no vértice P1, de coordenadas N {n_inicial} m. e E {e_inicial} m.; "
    
    dados_para_tabela = [] 

    for i in range(len(reordered) - 1):
        nome_atual = f"P{i+1}"
        nome_prox = "P1" if i == len(reordered) - 2 else f"P{i+2}"
        
        p_atual = reordered[i]
        p_prox = reordered[i+1]
        
        dist = p_atual.distance(p_prox)
        az_dec = p_atual.azimuth(p_prox)
        if az_dec < 0: az_dec += 360
        
        d = int(az_dec)
        m = int((az_dec - d) * 60)
        s = (az_dec - d - m/60) * 3600
        
        dist_formatada = formata_br(dist)
        n_prox = formata_br(p_prox.y())
        e_prox = formata_br(p_prox.x())
        
        dados_para_tabela.append({
            'de': nome_atual,
            'para': nome_prox,
            'az': f"{d}°{m:02d}'{s:02.0f}\"",
            'dist': dist_formatada,
            'e': e_prox,
            'n': n_prox
        })
        
        info_trecho = f"Azimute: {d}°{m:02d}'{s:02.0f}\" | Distância: {dist_formatada}m"
        
        linha_destaque = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        linha_destaque.setColor(QColor(255, 0, 0))
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
        loop_principal.exec_()
        
        resultado = dialog.result()
        linha_destaque.reset()
        
        if resultado == QDialog.Accepted:
            confrontante_txt = dialog.confrontante_edit.text()
            if not confrontante_txt.strip():
                confrontante_txt = "NÃO INFORMADO"
            
            texto_final += (f"deste, segue com azimute de {d}°{m:02d}'{s:02.0f}\" e distância de {dist_formatada} m., "
                            f"confrontando neste trecho com {confrontante_txt}, até o vértice {nome_prox}, "
                            f"de coordenadas N {n_prox} m. e E {e_prox} m.; ")
        else:
            QMessageBox.information(iface.mainWindow(), "Cancelado", "Geração do memorial interrompida.")
            return

    texto_final += "ponto inicial da descrição deste perímetro. Todas as coordenadas aqui descritas estão geo-referenciadas ao Sistema Geodésico Brasileiro Sirgas 2000. Todos os azimutes e distâncias, áreas e perímetros foram calculados no plano de projeção UTM. Obs.: Não consta área de APP."
    
    layer.startEditing()
    idx = layer.fields().indexFromName('Memorial')
    layer.changeAttributeValue(feat.id(), idx, texto_final)
    layer.commitChanges()
    
    resposta = QMessageBox.question(iface.mainWindow(), "Tabela de Coordenadas", 
                                    "Memorial salvo com sucesso!\n\nDeseja exportar a Tabela de Coordenadas em DXF?", 
                                    QMessageBox.Yes | QMessageBox.No)
    
    if resposta == QMessageBox.Yes:
        caminho_salvar, _ = QFileDialog.getSaveFileName(iface.mainWindow(), "Salvar Tabela DXF", "", "DXF Files (*.dxf)")
        if caminho_salvar:
            if not caminho_salvar.endswith('.dxf'):
                caminho_salvar += '.dxf'
            gerar_tabela_dxf(dados_para_tabela, caminho_salvar)
            QMessageBox.information(iface.mainWindow(), "Sucesso", "Tabela salva! Agora é só jogar no CAD.")