📖 Passo a Passo de Uso
Para gerar seu memorial descritivo e tabela de coordenadas, siga este roteiro:

Insira a geometria: Desenhe ou importe a geometria (polígono) do imóvel para o QGIS via DXF.

Dica para confrontantes: Caso não tenha os confrontantes no DXF, adicione uma camada vetorial do tipo ponto (.shp). Salve-a e deixe um campo simples (como con) para definir os confrontantes. Para editar, selecione essa camada, clique em Alternar Edição, adicione o ponto na testada da confrontação e informe o lote/quadra (se urbano) ou a matrícula imobiliária seguida do nome do proprietário.

⚠️ Atenção aos Cartórios (Precisão das Casas Decimais): Os Cartórios de Registro de Imóveis (RI) costumam exigir um grau de precisão geométrica irreal na conferência do memorial. Qualquer divergência de 1 cm é motivo de nota devolutiva. O erro mais comum é usar coordenadas com 3 casas decimais (milímetros) e distâncias com apenas 2 casas (centímetros) — essa diferença matemática de arredondamento altera os fechamentos! Para garantir a total compatibilidade e aceitação cartorária, utilize 3 casas decimais para TUDO (coordenadas, distâncias e percursos).

Selecione o polígono: Utilize a ferramenta de seleção do QGIS para destacar a feição que deseja descrever.

Acione o Memorial Interativo: Clique no ícone do plugin na sua barra de ferramentas.

Defina os confrontantes: Para cada trecho destacado, selecione no mapa o lote/texto vizinho ou insira as informações manualmente.

Complete o percurso: Repita o processo até percorrer todo o perímetro do imóvel.

Salve o memorial descritivo: Escolha o local de destino para gerar o arquivo editável (.doc).

Salve a tabela de coordenadas: Exporte os dados técnicos diretamente para um arquivo DXF (padrão CAD/Topograph).

💡 Nota da versão 2.2: O programa inicia a descrição automaticamente pelo ponto mais ao Norte (vértice P1) e segue no sentido horário para garantir a padronização técnica.

Se houver mais de uma gleba, você pode definir a sequência inicial da área seguinte. Por exemplo: ao importar um polígono de 4 vértices do lado oeste da via, você terá P1, P2, P3 e P4. No polígono de 6 vértices do lado leste, você pode definir a numeração inicial como 5, gerando P5, P6, P7, P8, P9 e P10. Lembre-se de que você também pode renomear os vértices manualmente caso prefira manter a nomenclatura oficial que consta na matrícula do confrontante!
