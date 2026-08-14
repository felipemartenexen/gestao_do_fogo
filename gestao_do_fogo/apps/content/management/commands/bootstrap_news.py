"""
Publica as notícias iniciais da rede sob a página de Notícias.

Idempotente: rodar de novo não duplica nem sobrescreve textos já editados no CMS -
posts que já existem são deixados como estão. Para repor o conteúdo original de um
post, apague-o no /cms/ e rode o comando outra vez.
"""

import json
from datetime import date
from typing import Any

from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder

from apps.content.models import BlogIndexPage, BlogPage

NEWS = [
    {
        "slug": "webinar-rede-fogo-pontes-para-uma-atuacao-integrada",
        "title": "Rede Fogo: pontes para uma atuação integrada",
        "date": date(2026, 7, 24),
        "intro": (
            "O terceiro webinar da Rede de Pesquisadores do Fogo reúne especialistas em ecologia e "
            "meio ambiente para discutir o papel das colaborações científicas. 24 de julho, 13h às 15h, no Zoom."
        ),
        "body": """
<p><strong>Sexta-feira, 24 de julho de 2026 &middot; 13h às 15h (horário de Brasília)
&middot; plataforma Zoom</strong></p>

<p>O terceiro webinar da Rede de Pesquisadores do Fogo reunirá especialistas para discutir pesquisas
no tema <em>Ecologia e meio ambiente</em>, com foco na importância das colaborações científicas.</p>

<h3>Apresentações desta edição</h3>
<ul>
  <li><strong>Fogo e a conservação da biodiversidade no Cerrado em transformação</strong> &mdash;
      Heitor Campos de Sousa (UnB) &middot; 15 min</li>
  <li><strong>Modelagem de risco de incêndio para iniciativas de restauração em larga escala no Brasil</strong> &mdash;
      Clarice Braúna Mendes (IIS) &middot; 15 min</li>
  <li><strong>O fogo em áreas úmidas: ecologia e desafios de manejo</strong> &mdash;
      Geraldo Alves Damasceno Junior (UFMS) &middot; 15 min</li>
  <li><strong>Inflamabilidade de combustíveis florestais da Amazônia brasileira</strong> &mdash;
      Bruno Polycarpo Palmerim Dias (CBMERJ / COPPE-UFRJ) &middot; 15 min</li>
</ul>

<h3>Como participar</h3>
<p>Acesse o webinar no Zoom:
<a href="https://us02web.zoom.us/j/89147740638" target="_blank" rel="noopener">us02web.zoom.us/j/89147740638</a><br>
Senha: <strong>151558</strong></p>

<p>Inscreva-se para participar e receber informações sobre os próximos webinars e eventos:
<a href="https://docs.google.com/forms/d/e/1FAIpQLSdhwePKfM4_uteAZzHpkTwprVR2xSsyjuqpfLg7UOOHyZ8yeA/viewform"
 target="_blank" rel="noopener">formulário de inscrição</a>.</p>

<p>Contribua com o mapeamento de pesquisadores(as) do fogo:
<a href="https://docs.google.com/forms/d/e/1FAIpQLSfoN7zhtgq1Myrd7oaHLFj_m0eNQ3oBLS-nOqUe7Az8WiOT8g/viewform"
   target="_blank" rel="noopener">formulário de mapeamento</a>.</p>

<p>As gravações dos webinars anteriores estão no canal do IPAM no YouTube
(<a href="https://www.youtube.com/watch?v=ZaBR1UXxiug" target="_blank" rel="noopener">@IPAMAmazonia</a>).</p>

<p>Dúvidas: Waira Machida &mdash;
<a href="mailto:waira.machida@ipam.org.br">waira.machida@ipam.org.br</a></p>
""",
    },
    {
        "slug": "mapbiomas-fogo-colecao-5",
        "title": "MapBiomas Fogo lança a Coleção 5 e o Relatório Anual do Fogo",
        "date": date(2026, 7, 21),
        "intro": (
            "Evento presencial em Brasília apresenta 41 anos de dinâmica do fogo nos biomas brasileiros e "
            "dois produtos novos: intervalo de retorno do fogo e severidade das áreas queimadas."
        ),
        "body": """
<p>No dia 21 de julho, o MapBiomas convida todos e todas para o lançamento da
<strong>Coleção 5 do MapBiomas Fogo</strong>, em evento presencial em Brasília.</p>

<p>O lançamento contará com a apresentação da segunda edição do <strong>Relatório Anual do Fogo (RAF)</strong>,
que reúne um panorama dos <strong>41 anos da dinâmica do fogo nos biomas brasileiros</strong>.</p>

<h3>Dois produtos novos</h3>
<ul>
  <li><strong>Intervalo de retorno do fogo</strong> &mdash; quanto tempo uma mesma área leva para voltar a
      queimar. Ajuda a entender os intervalos entre ocorrências ao longo dos anos e como eles variam
      entre regiões.</li>
  <li><strong>Severidade das áreas queimadas</strong> &mdash; o nível de alteração potencial causado pelo fogo.
      Nem todo fogo provoca os mesmos danos, e o produto permite identificar onde os impactos foram
      mais intensos.</li>
</ul>

<h3>Encerramento</h3>
<p>Além da programação de lançamento, haverá coquetel de encerramento com a apresentação do livreto
sobre o combate a incêndios em áreas florestais e da exposição fotográfica
<em>Entre a Chama e o Cuidado</em>, do PrevFogo.</p>

<h3>Serviço</h3>
<ul>
  <li><strong>Data:</strong> 21 de julho de 2026, das 13h30 às 18h</li>
  <li><strong>Local:</strong> Organização do Tratado de Cooperação Amazônica (OTCA) &mdash;
      510 Norte, Edifício Ministério da Saúde II, Bloco A, 3º andar, Brasília (DF)</li>
  <li><strong>Inscrições:</strong>
      <a href="https://forms.gle/pS9dk1sjBtAo9qHx6" target="_blank" rel="noopener">forms.gle/pS9dk1sjBtAo9qHx6</a></li>
</ul>

<p><em>Realização: MapBiomas. Apoio institucional: OTCA e Observatório Regional Amazônico (ORA).</em></p>
""",
    },
    {
        "slug": "queimadasr-pacote-em-r-para-dados-de-queimadas",
        "title": "queimadasR: pacote em R para os dados oficiais de queimadas",
        "date": date(2026, 7, 15),
        "intro": (
            "Desenvolvido em parceria com pesquisadores da UFRRJ e da Fiocruz, o pacote dá acesso direto "
            "aos dados do Programa Queimadas do INPE (BDQueimadas)."
        ),
        "body": """
<p>O <strong>queimadasR</strong> é um pacote em R desenvolvido para facilitar o acesso e a análise de
dados oficiais de queimadas no Brasil.</p>

<p>Criado em parceria com pesquisadores da <strong>UFRRJ</strong> e da <strong>Fiocruz</strong>, o pacote
permite acessar diretamente os dados do <strong>Programa Queimadas do INPE</strong> (BDQueimadas),
sem as etapas manuais de download e limpeza que costumam consumir boa parte do trabalho.</p>

<p>É uma ferramenta útil para pesquisadores, cientistas de dados e gestores que trabalham na
interface entre meio ambiente, clima e saúde pública.</p>

<p>Repositório e documentação:
<a href="https://github.com/wtassinari/queimadasR"
   target="_blank" rel="noopener">github.com/wtassinari/queimadasR</a></p>
""",
    },
]


class Command(BaseCommand):
    help = "Publica as notícias iniciais da rede sob a página de Notícias."

    def handle(self, **options: Any) -> None:
        index = BlogIndexPage.objects.filter(slug="noticias").first()
        if index is None:
            self.stderr.write(
                self.style.ERROR("Página de Notícias não encontrada. Rode `manage.py bootstrap_content` antes.")
            )
            return

        created = skipped = 0
        for item in NEWS:
            if BlogPage.objects.filter(slug=item["slug"]).exists():
                self.stdout.write(f"  já existe, mantendo: {item['title']}")
                skipped += 1
                continue

            post = BlogPage(
                slug=item["slug"],
                title=item["title"],
                date=item["date"],
                intro=item["intro"],
                body=json.dumps(
                    [{"type": "html", "value": item["body"].strip()}],
                    cls=DjangoJSONEncoder,
                ),
            )
            index.add_child(instance=post)
            post.save()
            post.save_revision().publish()
            self.stdout.write(self.style.SUCCESS(f"  publicado: {item['title']}"))
            created += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"publicados: {created} | já existiam: {skipped}"))
