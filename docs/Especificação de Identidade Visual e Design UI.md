# **Especificação de Identidade Visual e UI Design**

**Projeto:** Criação de Website Baseado no Sistema Visual "Talita Issei"

**Versão:** 1.0

## **1\. Direção Estratégica & Conceito da Marca**

A identidade visual se apoia na dualidade de dois ambientes de trabalho de uma empresária. O sistema intercala seções para criar ritmo de leitura, transitando entre uma "Fachada Editorial" e os "Bastidores Estratégicos".

### **O Sistema Dual de Interface**

* **Modo Claro (Editorial / Paper):** Representa clareza, autoridade e diagnóstico. Fundo branco impecável, tipografia serifada de alto luxo, leitura limpa de revista.  
* **Modo Escuro (Notepad / Bastidores):** Representa a "mão na massa", o método e a estratégia. Simula a interface do aplicativo *Apple Notes* (Bloco de Notas do iOS) no modo noturno, com marcações de texto selecionado.

**Personalidade da Marca:** Inteligente, direta, acolhedora, elegante e extremamente prática (sem jargões corporativos excessivos).

## **2\. Sistema de Cores (Tokens e Variáveis CSS)**

O projeto exige uma paleta restrita. O contraste entre o papel, a tinta escura e os detalhes em caramelo/âmbar é fundamental. O azul-ciano deve ser usado com extrema moderação (apenas para o selo de verificação/autoria).

| Token de Cor (CSS) | Código Hex | Aplicação / Função |
| :---- | :---- | :---- |
| \--bg-paper | \#FFFFFF | Fundo principal da versão clara (Hero, Serviços). |
| \--bg-warm-paper | \#FBFAF7 | Fundo alternativo claro (para suavizar a leitura em blocos longos). |
| \--bg-dark-notepad | \#121212 | Fundo da versão escura (Seção Método, Soluções). |
| \--text-ink-primary | \#111522 | Títulos e textos principais sobre fundo claro (Preto com leve fundo azul). |
| \--text-ink-muted | \#92949B | Textos de apoio sobre fundo claro (@handle, legendas, divisores). |
| \--text-dark-primary | \#F5F5F7 | Texto principal sobre fundo escuro (Branco suave / Off-white). |
| \--accent-amber | \#EAA034 | Textos e ícones estilo iOS (\< Notas), numeração de etapas. |
| \--highlight-caramel | \#9E7138 | Fundo do "grifo" (marca-texto) de palavras-chave no modo escuro. |
| \--highlight-pin | \#E7D6C2 | Cor das bolinhas (pinos) nas pontas da seleção de texto. |
| \--verified-cyan | \#13C4E5 | Exclusivo para o selo de autoridade / verificação no topo. |
| \--check-green | \#5C9E31 | Fundo dos ícones de "Check" quadrado no diagnóstico. |

## **3\. Tipografia e Hierarquia**

A força do design reside no contraste entre uma **Serifada de Exibição** (elegante, com contraste alto entre hastes finas e grossas) e uma **Sans-Serif de Interface** (limpa e técnica).

### **3.1 Famílias Tipográficas**

* **Primária (Serifada):** DM Serif Display, Libre Baskerville ou Cormorant Garamond.  
  * *Uso:* Títulos (H1, H2), diagnósticos, texto dos checklists, nome da autora.  
* **Secundária (Sans-Serif):** Inter, SF Pro Display (ou Apple System), Manrope.  
  * *Uso:* Identificador @handle, navegação de topo, botões, microtextos, metadados.

### **3.2 Tabela de Hierarquia (Guia para o Desenvolvedor)**

| Nível / Elemento | Família | Peso / Estilo | Tamanho Sugerido (Desktop) | Tamanho Sugerido (Mobile) |
| :---- | :---- | :---- | :---- | :---- |
| **Nome da Autora** | Serifada | Bold (700) | 32px | 24px |
| **Identificador (@)** | Sans-Serif | Regular (400) | 16px | 14px |
| **Título Principal (H1)** | Serifada | Regular / Bold | 56px \- 64px | 36px \- 42px |
| **Diagnóstico (Frase 1\)** | Serifada | Bold (700) | 32px | 24px |
| **Checklist (Dor)** | Serifada | Regular (400) | 24px | 18px |
| **Checklist (Método)** | Serifada | Itálico (400i) | 24px | 18px |
| **Interface iOS (Notas)** | Sans-Serif | Semibold (600) | 18px | 16px |

## **4\. Anatomia de Componentes Exclusivos**

Estes são os "Signature Elements" (Elementos de Assinatura) que devem ser construídos no front-end para replicar a estética dos cards.

### **4.1 Cabeçalho de Autoria (Modo Claro)**

* **Estrutura:** Fotografia circular (avatar) à esquerda \+ \[Nome da Autora e Selo de Verificação na mesma linha\] \+ \[@handle abaixo do nome em cinza\].  
* **Avatar:** Proporção 1:1, bordas totalmente arredondadas (border-radius: 50%), ocupando cerca de 48px a 64px.  
* **Selo de Verificação:** Ícone de roseta/estrela poligonal preenchido na cor \--verified-cyan com um "check" branco no centro. Deve ficar imediatamente após o nome.

### **4.2 O "Grifo de Seleção iOS" (Modo Escuro) \- *Crucial***

Deve ser aplicado em trechos curtos ou palavras-chave dentro de títulos no fundo escuro, simulando a seleção nativa de texto do iPhone.

* **Background:** Caixa com a cor \--highlight-caramel (com leve transparência, ex: rgba(158, 113, 56, 0.6)).  
* **Pinos (Handles):** Dois elementos circulares na cor \--highlight-pin acompanhados de uma fina linha vertical.  
  * O pino 1 fica no topo esquerdo do trecho selecionado.  
  * O pino 2 fica na base direita do trecho selecionado.

### **4.3 Topo "Apple Notes" (Modo Escuro)**

No topo das seções escuras, deve haver um "falso header" de aplicativo:

* **Esquerda:** Ícone de chevron para a esquerda (\<) seguido da palavra "Notas", ambos na cor \--accent-amber. Fonte: Sans-serif, bold.  
* **Direita:** Ícone de reticências (...) na mesma cor \--accent-amber.

### **4.4 Divisor Editorial (Modo Claro)**

Usado para separar blocos de texto (ex: entre o checklist e a chamada de ação final).

* **Estilo:** Linha sólida, preta (--text-ink-primary), alinhada à esquerda.  
* **Dimensões:** Espessura grossa (aprox. 3px a 4px), largura curta (aprox. 96px a 120px). Não deve cruzar a tela toda.

### **4.5 Componentes de Checklist**

* **Estilo A (Modo Claro \- Diagnóstico de Dor):** Marcador é um quadrado verde arredondado com um check branco. A fonte é Serifada Regular.  
* **Estilo B (Modo Escuro \- Execução do Método):** Marcador usa a sintaxe textual \[ \] na cor cinza/âmbar. A fonte é Serifada Itálica.

## **5\. Estrutura de Layout e Grid (UX/UI)**

A composição deve respirar. A inspiração é o formato de leitura em formato retrato (4:5).

* **Alinhamento Central do Container:** O site pode ocupar a largura toda da tela (full-width) para as faixas de fundo, mas o conteúdo (texto e elementos) deve ficar restrito a um container central estreito (ex: max-width de 680px a 760px), simulando a largura confortável de leitura de um post ou coluna de jornal.  
* **Alinhamento de Texto:** O padrão ouro desta identidade é o **Alinhamento à Esquerda**. Títulos, listas, divisores e botões devem seguir uma linha guia invisível à esquerda. Evite centralizar blocos de texto longo.  
* **Espaçamento (Padding/Margin):** Use a regra de 8px. Mantenha áreas de respiro muito generosas (ex: 80px a 120px entre grandes seções; 40px a 56px entre o título e os parágrafos).

## **6\. O Que Fazer e O Que Evitar**

| Fazer (Do's) | Evitar (Don'ts) |
| :---- | :---- |
| **Alternar seções inteiras** em blocos Claro \-\> Escuro \-\> Claro para manter a dualidade (Editorial vs. Bastidores). | **Não misturar o padrão escuro no claro.** O "Top Apple Notes" só existe no fundo escuro. |
| **Usar fotos reais, orgânicas e iluminadas** da especialista em recortes limpos (circulares ou com cantos sutilmente arredondados). | **Evitar fotos excessivamente manipuladas** ou uso excessivo de imagens de banco de imagens genéricas. |
| Manter as listas curtas, fáceis de escanear visualmente (3 a 5 itens por lista). | Evitar textos justificados ou centralizados. |
| Usar CTAs diretos e conversacionais (Ex: *"Continuar leitura da legenda"* \> *"Conhecer o método"*). | Evitar botões gradientes, bordas arredondadas excessivas (estilo pílula) e sombras pesadas (Drop-shadows). |

