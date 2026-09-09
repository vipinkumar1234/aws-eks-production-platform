'use strict';
const $ = id => document.getElementById(id);
let room = null, busy = false, signedIn = false, polling = false;
const cells = [...document.querySelectorAll('.cell')];
function notice(message = '') { $('notice').textContent = message; $('notice').hidden = !message; }
async function api(path, method = 'GET', data) {
  const response = await fetch(path, {method, credentials: 'same-origin', cache: 'no-store',
    ...(method !== 'GET' ? {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data || {})} : {})});
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401) { signedIn = false; $('welcome').hidden = false; $('lobby').hidden = true; $('logout').hidden = true; }
    throw new Error(result.error || 'The service is unavailable. Please try again.');
  }
  return result;
}
function paint() {
  if (!room) return;
  $('mode-label').textContent = room.mode === 'solo' ? 'SOLO CHALLENGE' : 'PRIVATE FRIEND MATCH';
  $('round-label').textContent = `ROUND ${room.round}`;
  $('x-label').textContent = room.you === 'X' ? 'You' : 'Your friend';
  $('o-label').textContent = room.mode === 'solo' ? 'Computer' : room.you === 'O' ? 'You' : room.opponent_joined ? 'Your friend' : 'Waiting…';
  $('x-score').textContent = room.scores.X; $('o-score').textContent = room.scores.O;
  $('draws').textContent = `${room.scores.draw} ${room.scores.draw === 1 ? 'DRAW' : 'DRAWS'} · YOU ARE ${room.you}`;
  let title = 'The game is on.', status = room.turn === room.you ? 'Your turn. Find your winning move.' : 'Your friend is thinking. Hang tight.';
  if (room.status === 'waiting') { title = 'A rivalry in the making.'; status = 'Copy your invite and send it to a friend.'; }
  if (room.status === 'won') { title = room.winner === room.you ? 'That’s your game. Well played!' : 'A good game. One more?'; status = `${room.winner} takes the round. Ready for a rematch?`; }
  if (room.status === 'draw') { title = 'Great minds. Even match.'; status = 'A draw! There’s always the next round.'; }
  if (room.rematch.length) status = room.rematch.includes(room.you) ? 'Rematch requested. Waiting for your friend.' : 'Your friend wants a rematch. Are you in?';
  $('game-title').textContent = title; $('game-status').textContent = status;
  $('player-x').classList.toggle('active', room.status === 'playing' && room.turn === 'X');
  $('player-o').classList.toggle('active', room.status === 'playing' && room.turn === 'O');
  cells.forEach((cell, index) => {
    cell.textContent = room.board[index]; cell.className = `cell ${room.board[index].toLowerCase()} ${room.winning_line.includes(index) ? 'win' : ''}`;
    cell.disabled = busy || !signedIn || room.status !== 'playing' || room.turn !== room.you || !!room.board[index];
    cell.setAttribute('aria-label', `Square ${index + 1}, ${room.board[index] || 'empty'}`);
  });
  $('rematch').hidden = !['won', 'draw'].includes(room.status);
  $('rematch').disabled = busy || room.rematch.includes(room.you);
  $('invite').hidden = room.mode !== 'friend' || room.opponent_joined;
  $('invite-link').value = `${location.origin}/?room=${room.game_id}`;
  sessionStorage.setItem('arena-room', room.game_id);
  $('resume').hidden = true;
}
async function action(callback) {
  if (busy) return;
  busy = true; notice(); paint();
  try { await callback(); }
  catch (error) { notice(error.message); if (room && signedIn) { try { room = await api(`/api/rooms/${room.game_id}`); } catch (_) {} } }
  finally { busy = false; paint(); }
}
for (const mode of ['solo', 'friend']) $(mode).addEventListener('click', () => action(async () => { room = await api('/api/rooms', 'POST', {mode}); }));
cells.forEach(cell => cell.addEventListener('click', () => action(async () => { room = await api(`/api/rooms/${room.game_id}/move`, 'POST', {position: Number(cell.dataset.position), version: room.version}); })));
$('rematch').addEventListener('click', () => action(async () => { room = await api(`/api/rooms/${room.game_id}/rematch`, 'POST', {version: room.version}); }));
function roomCode(input) {
  const value = input.trim();
  try { return new URL(value).searchParams.get('room') || ''; } catch (_) { return value.toLowerCase(); }
}
$('join-form').addEventListener('submit', event => { event.preventDefault(); action(async () => {
  const code = roomCode($('room-code').value);
  if (!/^[0-9a-f]{16}$/.test(code)) throw new Error('Paste the complete invite link or 16-character room code.');
  room = await api(`/api/rooms/${code}/join`, 'POST'); history.replaceState({}, '', '/');
}); });
$('copy-invite').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText($('invite-link').value); $('copy-invite').textContent = 'Copied!'; setTimeout(() => $('copy-invite').textContent = 'Copy invite', 1800); }
  catch (_) { $('invite-link').select(); notice('Select and copy the invite link above.'); }
});
$('logout').addEventListener('click', () => action(async () => { const result = await api('/api/logout', 'POST'); sessionStorage.clear(); location.assign(result.redirect); }));
$('resume-button').addEventListener('click', () => action(async () => { room = await api(`/api/rooms/${sessionStorage.getItem('arena-room')}`); }));
async function start() {
  const invite = new URL(location.href).searchParams.get('room');
  if (invite && /^[0-9a-f]{16}$/.test(invite)) sessionStorage.setItem('arena-invite', invite);
  try {
    const user = await api('/api/me'); signedIn = true;
    $('identity').textContent = user.email; $('welcome').hidden = true; $('lobby').hidden = false; $('logout').hidden = false;
    const pendingInvite = sessionStorage.getItem('arena-invite');
    if (pendingInvite) { $('room-code').value = pendingInvite; notice('Your invite is ready. Select Join to take your seat.'); sessionStorage.removeItem('arena-invite'); }
    else if (sessionStorage.getItem('arena-room')) $('resume').hidden = false;
  } catch (error) { if (!$('welcome').hidden) return; notice(error.message); }
}
setInterval(async () => {
  if (!room || !signedIn || busy || polling || document.hidden || room.mode !== 'friend') return;
  polling = true;
  try { const updated = await api(`/api/rooms/${room.game_id}`); if (!busy && updated.game_id === room.game_id && updated.version >= room.version) { room = updated; paint(); } }
  catch (error) { notice(error.message); }
  finally { polling = false; }
}, 2500);
start();
