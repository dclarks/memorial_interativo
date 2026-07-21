📖 Passo a Passo de Uso

Para gerar seu memorial e tabela com perfeição, siga este roteiro:

1 - Insira o polígono: Desenhe ou importe a geometria (linha ou polígono) do imóvel para o QGIS via dxf. Caso não tenha os confrontantes no dxf, adicione uma camada de vetor .shp do tipo ponto, salve ela, pode apagar o index, deixe apenas con ou algo assim para definir os confrontantes. Quando for editar os confrontantes, selecione esse layer, clique em editar e selecione adicionar ponto, clique no mapa e adicione o ponto na testada da confrontação e coloque o lote, quadra, se for urbano, ou apenas a matricula imobiliaria do imóvel e se possível seguido com o nome do proprietário para efeito de cartório de registro de imóveis, gostam de tudo completo, até as casas eles exigem que sejam perfeitamente casadas, cuide do erro de arredondamento, pode ate colocar distancia em cm, e coordenada em milimetros, não é coerente, mas eles aceitam, não existe engenheiro nos cartórios. 

2 - Selecione o polígono: Utilize a ferramenta de seleção do QGIS para destacar a feição que deseja descrever.

3 - Acione o botão do Memorial Interativo: Clique no ícone do plugin na sua barra de ferramentas.

4 - Defina os confrontantes: Para cada trecho destacado, selecione no mapa o lote/texto vizinho ou insira as informações manualmente.

5 - Complete o tour: Repita o processo até percorrer todo o perímetro do imóvel.

6 - Salve o memorial descritivo: Escolha o local para gerar o arquivo de texto (.doc).

7 - Salve a tabela de coordenadas: Exporte os dados técnicos diretamente para um arquivo DXF (padrão CAD/Topograph).


obs.: Na versão 2.2, o programa inicia a descrição automaticamente pelo ponto mais ao Norte (vértice P1) e segue sempre no sentido horário para garantir a padronização técnica. Se houve mais de uma gleba você pode definir a sequência dos pontos da gleba seguinte, por exemplo, importar um poligon de 4 vértices do lado oeste da via, você vai ter os vértices P1, P2, P3 e P4, no polígono do lado leste da via, se o poligono for de 6 vértices, você pode definir o número 5 para ele iniciar, vai ficar: P5, P6, P7, P8, P9 e P10, lembrando que pode alterar o nome caso haja em matrícula do confrontante o nome do vértice e quiser deixar igual!.
