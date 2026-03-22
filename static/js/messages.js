// Messagerie interne — auto-refresh, scroll, compteur caractères

function initConversation(convId, lastMsgId, currentUserId) {
  var _lastId = lastMsgId;

  // Scroll to bottom on load
  var thread = document.getElementById('msgThread');
  if (thread) thread.scrollTop = thread.scrollHeight;

  // Character counter
  var input = document.getElementById('msgInput');
  var counter = document.getElementById('charCount');
  if (input && counter) {
    input.addEventListener('input', function() {
      counter.textContent = input.value.length + ' / 2000';
      counter.style.color = input.value.length > 1800 ? '#dc3545' : '';
    });
    // Submit with Ctrl+Enter / Cmd+Enter
    input.addEventListener('keydown', function(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        var form = document.getElementById('sendForm');
        if (form) form.submit();
      }
    });
  }

  // Auto-refresh polling every 15s
  if (!convId) return;
  function poll() {
    fetch('/messages/' + convId + '/api/since/' + _lastId)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (!data.messages || data.messages.length === 0) return;
        data.messages.forEach(function(m) {
          appendMessage(m, currentUserId);
          if (m.id > _lastId) _lastId = m.id;
        });
        if (thread) thread.scrollTop = thread.scrollHeight;
        // Remove empty state if present
        var empty = thread ? thread.querySelector('.text-center.text-muted') : null;
        if (empty) empty.remove();
      })
      .catch(function() {});
  }
  setInterval(poll, 15000);
}

function appendMessage(m, currentUserId) {
  var thread = document.getElementById('msgThread');
  var bottom = document.getElementById('bottom');
  if (!thread || !bottom) return;
  if (document.getElementById('msg-' + m.id)) return;

  var isMe = m.is_me || m.sender_id === currentUserId;
  var initials = m.sender_name ? m.sender_name.charAt(0).toUpperCase() : '?';
  var avatarStyle = isMe
    ? 'background:linear-gradient(135deg,#0d6efd,#0dcaf0);'
    : 'background:linear-gradient(135deg,#6c757d,#adb5bd);';

  var bodyHtml = m.body.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');

  var html = '<div class="d-flex ' + (isMe ? 'justify-content-end msg-me' : 'justify-content-start msg-other') +
    ' align-items-end gap-2" id="msg-' + m.id + '">';

  if (!isMe) {
    html += '<div class="avatar-sm flex-shrink-0" style="' + avatarStyle + '">' + initials + '</div>';
  }

  html += '<div class="d-flex flex-column ' + (isMe ? 'align-items-end' : 'align-items-start') + '">';
  if (!isMe) {
    html += '<small class="text-muted mb-1">' + escHtml(m.sender_name) + '</small>';
  }
  html += '<div class="msg-bubble px-3 py-2 shadow-sm">' + bodyHtml + '</div>';
  html += '<div class="d-flex align-items-center gap-2 mt-1"><small class="text-muted" style="font-size:.75rem;">' +
    escHtml(m.created_at) + '</small></div>';
  html += '</div>';

  if (isMe) {
    html += '<div class="avatar-sm flex-shrink-0" style="' + avatarStyle + '">' + initials + '</div>';
  }
  html += '</div>';

  var div = document.createElement('div');
  div.innerHTML = html;
  thread.insertBefore(div.firstChild, bottom);
}

function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Update navbar unread badge globally
function updateUnreadBadge() {
  fetch('/messages/api/unread')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var badges = document.querySelectorAll('.msg-unread-badge');
      badges.forEach(function(b) {
        if (data.unread > 0) {
          b.textContent = data.unread;
          b.style.display = '';
        } else {
          b.style.display = 'none';
        }
      });
    })
    .catch(function() {});
}

// Poll unread count every 30s on all pages, and once immediately on load
if (document.querySelector('.msg-unread-badge') !== null) {
  updateUnreadBadge();
  setInterval(updateUnreadBadge, 30000);
}
