# Músicas

Repertório do louvor, músicas tocadas em cada domingo, setlist do próximo domingo, cifras,
letras e hinário, além de estatísticas de uso do hinário no app.

## O que existe

- Lista de músicas e de músicas tocadas por domingo
- Mais tocadas e tons mais usados
- Sugestão de 4 músicas para o domingo (não repete o que tocou nos últimos 90 dias)
- Registrar o que foi tocado no domingo (até 10 músicas)
- Setlist do domingo: salvar, ver a próxima, ver as pendentes de confirmação
- Push para o grupo do Louvor quando a setlist é salva
- Lembrete por push no domingo à noite para confirmar o que foi tocado
- Cifras e letras: listar, criar, editar
- Hinário
- Histórico de hinos abertos no app: relatório por período e ranking
- Configurações do histórico e horários dos cultos para o relatório

## Quem acessa

| Quem                      | O quê                                              |
|---------------------------|----------------------------------------------------|
| Qualquer um               | músicas, estatísticas, sugestão, cifras, letras, hinário |
| Membro do Louvor          | ver a próxima setlist                              |
| Liderança, Admin          | registrar tocadas, cifras, letras, ver setlists    |
| Liderança/Admin do Louvor | salvar setlist e receber o lembrete                |
| Mídia, Liderança, Admin   | relatórios do hinário                              |
| Admin                     | configurações do hinário e horários dos cultos     |

## Endpoints

```
GET    api/songs/
GET    api/songs-by-sunday/
GET    api/top-songs/
GET    api/top-tones/
GET    api/suggested-songs/?fixed=1:12,3:45
POST   api/played/register/
GET    api/setlists/current/
GET    api/setlists/pending-confirmation/
GET    api/setlists/{data}/                PUT
GET    api/chord-charts/                   POST
PATCH  api/chord-charts/{id}/
GET    api/lyrics/                         POST
PATCH  api/lyrics/{id}/
GET    api/hymnal/
POST   api/hymnal-history/events/
GET    api/hymnal-history/occurrences/
GET    api/hymnal-history/top-hymns/
GET    api/hymnal-history/settings/        PATCH
GET    api/hymnal-history/service-windows/ POST
PATCH  api/hymnal-history/service-windows/{id}/   DELETE
```

## Atenção

- "Membro do Louvor" significa conta vinculada a um membro do ministério chamado
  **"Louvor"**. Renomear esse ministério desliga a setlist.
- Setlist é o plano e `Played` é o que tocou de fato. Registrar qualquer música tocada na
  data encerra o lembrete.
- Sugestão usa as posições 1-4 e registro aceita 1-10. É de propósito, não é bug.
- O lembrete roda num loop do `compose.prod.yml` (`send_setlist_reminders`), a cada 60 s.
- `hymnal-history/events/` é a única escrita aberta sem login, com throttle.

Detalhes: [`specs/songs/spec.md`](../../specs/songs/spec.md)
