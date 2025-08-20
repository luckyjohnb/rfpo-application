// RFPO Team Admin UI JS

document.addEventListener('DOMContentLoaded', function() {
  if (window.location.pathname === '/admin/teams') {
    loadTeams();
    document.getElementById('team-search').addEventListener('input', loadTeams);
    document.getElementById('team-form').addEventListener('submit', submitTeamForm);
  }
});

function getAuthHeader() {
  // Assumes JWT is stored in localStorage under 'token'
  const token = localStorage.getItem('token');
  return token ? { 'Authorization': 'Bearer ' + token } : {};
}

function loadTeams() {
  const search = document.getElementById('team-search').value;
  fetch(`/api/teams?search=${encodeURIComponent(search)}`, {
    headers: { ...getAuthHeader() }
  })
    .then(r => r.json())
    .then(data => renderTeams(data.teams || []));
}

function renderTeams(teams) {
  const list = document.getElementById('teams-list');
  if (!teams.length) {
    list.innerHTML = '<div class="alert alert-info">No teams found.</div>';
    return;
  }
  list.innerHTML = `<table class="table table-bordered"><thead><tr><th>Name</th><th>Abbrev</th><th>Consortium</th><th>Active</th><th>Actions</th></tr></thead><tbody>${teams.map(t => `
    <tr>
      <td>${t.name}</td>
      <td>${t.abbrev}</td>
      <td>${t.consortium_id}</td>
      <td>${t.active ? 'Yes' : 'No'}</td>
      <td>
        <button class="btn btn-sm btn-secondary" onclick="editTeam(${t.id})">Edit</button>
        <button class="btn btn-sm btn-${t.active ? 'warning' : 'success'}" onclick="toggleTeamStatus(${t.id}, ${t.active})">${t.active ? 'Deactivate' : 'Activate'}</button>
      </td>
    </tr>`).join('')}</tbody></table>`;
}

function showTeamForm(team) {
  document.getElementById('team-form-modal').style.display = 'block';
  document.getElementById('team-id').value = team ? team.id : '';
  document.getElementById('team-name').value = team ? team.name : '';
  document.getElementById('team-abbrev').value = team ? team.abbrev : '';
  document.getElementById('team-description').value = team ? team.description : '';
  document.getElementById('team-consortium-id').value = team ? team.consortium_id : '';
  document.getElementById('team-viewers').value = team ? (team.viewer_user_ids || []).join(',') : '';
  document.getElementById('team-limited-admins').value = team ? (team.limited_admin_user_ids || []).join(',') : '';
  document.getElementById('team-active').checked = team ? team.active : true;
}

function hideTeamForm() {
  document.getElementById('team-form-modal').style.display = 'none';
}

function editTeam(id) {
  fetch(`/api/teams/${id}`, { headers: { ...getAuthHeader() } })
    .then(r => r.json())
    .then(data => showTeamForm(data.team));
}

function submitTeamForm(e) {
  e.preventDefault();
  const id = document.getElementById('team-id').value;
  const payload = {
    name: document.getElementById('team-name').value,
    abbrev: document.getElementById('team-abbrev').value,
    description: document.getElementById('team-description').value,
    consortium_id: document.getElementById('team-consortium-id').value,
    viewer_user_ids: document.getElementById('team-viewers').value.split(',').map(s => s.trim()).filter(Boolean),
    limited_admin_user_ids: document.getElementById('team-limited-admins').value.split(',').map(s => s.trim()).filter(Boolean),
    active: document.getElementById('team-active').checked
  };
  const method = id ? 'PUT' : 'POST';
  const url = id ? `/api/teams/${id}` : '/api/teams';
  fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify(payload)
  })
    .then(r => r.json())
    .then(() => { hideTeamForm(); loadTeams(); });
}

function toggleTeamStatus(id, isActive) {
  const url = `/api/teams/${id}/${isActive ? 'deactivate' : 'activate'}`;
  fetch(url, { method: 'POST', headers: { ...getAuthHeader() } })
    .then(() => loadTeams());
}
