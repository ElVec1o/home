const express = require('express');
const cors = require('cors');
const fs = require('fs').promises;
const fsSync = require('fs');
const path = require('path');
const simpleGit = require('simple-git');
const { exec } = require('child_process');
const multer = require('multer');

const app = express();
const PORT = 3333;

// Paths
const DATA_DIR = path.join(__dirname, '..', 'src', 'data');
const REPO_DIR = path.join(__dirname, '..');
const PUBLIC_DIR = path.join(__dirname, '..', 'public');
const IMG_DIR = path.join(PUBLIC_DIR, 'img');
const git = simpleGit(REPO_DIR);

// Multer setup for file uploads
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const folder = req.body.folder || 'img';
    const destPath = path.join(PUBLIC_DIR, folder);
    // Create folder if it doesn't exist
    if (!fsSync.existsSync(destPath)) {
      fsSync.mkdirSync(destPath, { recursive: true });
    }
    cb(null, destPath);
  },
  filename: (req, file, cb) => {
    // Keep original name or use custom name
    const customName = req.body.customName;
    const filename = customName || file.originalname;
    cb(null, filename);
  }
});
const upload = multer({ storage, limits: { fileSize: 50 * 1024 * 1024 } }); // 50MB max

app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// Serve sample XML file
app.get('/sample-writeups-import.xml', (req, res) => {
  res.sendFile(path.join(__dirname, 'sample-writeups-import.xml'));
});

// Helper: Read JSON file
async function readData(filename) {
  const filepath = path.join(DATA_DIR, filename);
  const content = await fs.readFile(filepath, 'utf-8');
  return JSON.parse(content);
}

// Helper: Write JSON file
async function writeData(filename, data) {
  const filepath = path.join(DATA_DIR, filename);
  await fs.writeFile(filepath, JSON.stringify(data, null, 2) + '\n');
}

// Helper: Git commit and push
async function gitPush(message) {
  try {
    await git.add('.');
    await git.commit(message);
    await git.push('origin', 'main');
    return { success: true, message: 'Pushed to GitHub' };
  } catch (err) {
    // Check if it's just "nothing to commit"
    if (err.message.includes('nothing to commit')) {
      return { success: true, message: 'No changes to push' };
    }
    return { success: false, message: err.message };
  }
}

// ============ API ROUTES ============

// GET all data
app.get('/api/breaks', async (req, res) => {
  try {
    const data = await readData('breaks.json');
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/books', async (req, res) => {
  try {
    const data = await readData('books.json');
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/files', async (req, res) => {
  try {
    const data = await readData('files.json');
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/config', async (req, res) => {
  try {
    const data = await readData('site-config.json');
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/writeups', async (req, res) => {
  try {
    const data = await readData('writeups.json');
    res.json(data);
  } catch (err) {
    // Return empty array if file doesn't exist yet
    res.json([]);
  }
});

app.post('/api/writeups', async (req, res) => {
  try {
    await writeData('writeups.json', req.body.data);
    if (req.body.push) {
      const result = await gitPush('Update writeups via CMS');
      return res.json(result);
    }
    res.json({ success: true, message: 'Saved locally' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// SAVE all data (with optional auto-push)
app.post('/api/breaks', async (req, res) => {
  try {
    await writeData('breaks.json', req.body.data);
    if (req.body.push) {
      const result = await gitPush('Update breaks via CMS');
      return res.json(result);
    }
    res.json({ success: true, message: 'Saved locally' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/books', async (req, res) => {
  try {
    await writeData('books.json', req.body.data);
    if (req.body.push) {
      const result = await gitPush('Update books via CMS');
      return res.json(result);
    }
    res.json({ success: true, message: 'Saved locally' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/files', async (req, res) => {
  try {
    await writeData('files.json', req.body.data);
    if (req.body.push) {
      const result = await gitPush('Update files via CMS');
      return res.json(result);
    }
    res.json({ success: true, message: 'Saved locally' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/config', async (req, res) => {
  try {
    await writeData('site-config.json', req.body.data);
    if (req.body.push) {
      const result = await gitPush('Update site config via CMS');
      return res.json(result);
    }
    res.json({ success: true, message: 'Saved locally' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Manual push endpoint
app.post('/api/push', async (req, res) => {
  try {
    const message = req.body.message || 'Update via CMS';
    const result = await gitPush(message);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Git status
app.get('/api/git-status', async (req, res) => {
  try {
    const status = await git.status();
    res.json({
      modified: status.modified,
      created: status.created,
      deleted: status.deleted,
      staged: status.staged,
      ahead: status.ahead,
      behind: status.behind,
      clean: status.isClean()
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Execute shell command (for fixes)
app.post('/api/exec', async (req, res) => {
  const { command } = req.body;

  // Whitelist of allowed commands for safety
  const allowedCommands = [
    'rm -f',
    'git pull',
    'git push',
    'git status',
    'git remote set-url',
    'gh auth'
  ];

  const isAllowed = allowedCommands.some(cmd => command.startsWith(cmd) || command.includes(cmd));
  if (!isAllowed) {
    return res.status(403).json({ success: false, message: 'Command not allowed for safety reasons' });
  }

  exec(command, { cwd: REPO_DIR }, (error, stdout, stderr) => {
    if (error) {
      return res.json({ success: false, message: stderr || error.message, stdout, stderr });
    }
    res.json({ success: true, message: stdout || 'Command executed successfully', stdout, stderr });
  });
});

// Switch to SSH remote
app.post('/api/use-ssh', async (req, res) => {
  exec('git remote set-url origin git@github.com:ElVec1o/home.git', { cwd: REPO_DIR }, (error, stdout, stderr) => {
    if (error) {
      return res.json({ success: false, message: stderr || error.message });
    }
    res.json({ success: true, message: 'Switched to SSH. Now try pushing again.' });
  });
});

// Get current git remote
app.get('/api/git-remote', async (req, res) => {
  exec('git remote get-url origin', { cwd: REPO_DIR }, (error, stdout, stderr) => {
    if (error) {
      return res.json({ remote: null, error: stderr || error.message });
    }
    res.json({ remote: stdout.trim() });
  });
});

// SSH Key management
const os = require('os');
const SSH_DIR = path.join(os.homedir(), '.ssh');
const SSH_KEY_PATH = path.join(SSH_DIR, 'id_ed25519');
const SSH_PUB_PATH = path.join(SSH_DIR, 'id_ed25519.pub');

app.post('/api/ssh/generate', async (req, res) => {
  // Create .ssh directory if it doesn't exist
  exec(`mkdir -p ${SSH_DIR} && ssh-keygen -t ed25519 -f ${SSH_KEY_PATH} -N "" -C "cms@elvec1o"`, (error, stdout, stderr) => {
    if (error && !stderr.includes('already exists')) {
      return res.json({ success: false, message: stderr || error.message });
    }
    // Read the public key
    require('fs').readFile(SSH_PUB_PATH, 'utf8', (err, data) => {
      if (err) {
        return res.json({ success: false, message: 'Key generated but could not read public key' });
      }
      res.json({ success: true, publicKey: data.trim() });
    });
  });
});

app.get('/api/ssh/check', async (req, res) => {
  require('fs').readFile(SSH_PUB_PATH, 'utf8', (err, data) => {
    if (err) {
      return res.json({ exists: false });
    }
    res.json({ exists: true, publicKey: data.trim() });
  });
});

app.get('/api/ssh/test', async (req, res) => {
  exec('ssh -T git@github.com -o StrictHostKeyChecking=no 2>&1', (error, stdout, stderr) => {
    const output = stdout + stderr;
    // GitHub returns exit code 1 but with success message
    if (output.includes('successfully authenticated')) {
      return res.json({ success: true, message: 'SSH connection to GitHub works!' });
    }
    res.json({ success: false, message: output || 'Connection failed' });
  });
});

// GitHub token authentication
app.post('/api/auth/token', async (req, res) => {
  const { token } = req.body;
  if (!token) {
    return res.json({ success: false, message: 'No token provided' });
  }

  // Update remote URL with token
  const newUrl = `https://${token}@github.com/ElVec1o/home.git`;
  exec(`git remote set-url origin "${newUrl}"`, { cwd: REPO_DIR }, (error, stdout, stderr) => {
    if (error) {
      return res.json({ success: false, message: stderr || error.message });
    }
    res.json({ success: true, message: 'Token configured successfully' });
  });
});

// ============ FILE UPLOAD ============

// Upload file(s)
app.post('/api/upload', upload.array('files', 20), async (req, res) => {
  try {
    const files = req.files;
    if (!files || files.length === 0) {
      return res.json({ success: false, message: 'No files uploaded' });
    }

    const folder = req.body.folder || 'img';
    const results = files.map(f => ({
      filename: f.filename,
      path: `/${folder}/${f.filename}`,
      size: f.size
    }));

    res.json({ success: true, files: results, message: `${files.length} file(s) uploaded` });
  } catch (err) {
    res.json({ success: false, message: err.message });
  }
});

// List files in a folder
app.get('/api/files-list/:folder?', async (req, res) => {
  try {
    const folder = req.params.folder || 'img';
    const folderPath = path.join(PUBLIC_DIR, folder);

    if (!fsSync.existsSync(folderPath)) {
      return res.json({ files: [], folder });
    }

    const items = await fs.readdir(folderPath, { withFileTypes: true });
    const files = [];

    for (const item of items) {
      if (item.name.startsWith('.')) continue;
      const itemPath = path.join(folderPath, item.name);
      const stats = await fs.stat(itemPath);

      files.push({
        name: item.name,
        path: `/${folder}/${item.name}`,
        isDirectory: item.isDirectory(),
        size: stats.size,
        modified: stats.mtime
      });
    }

    // Sort: folders first, then by name
    files.sort((a, b) => {
      if (a.isDirectory !== b.isDirectory) return b.isDirectory - a.isDirectory;
      return a.name.localeCompare(b.name);
    });

    res.json({ files, folder });
  } catch (err) {
    res.json({ files: [], error: err.message });
  }
});

// Delete file
app.delete('/api/files-delete', async (req, res) => {
  try {
    const { filepath } = req.body;
    if (!filepath) {
      return res.json({ success: false, message: 'No filepath provided' });
    }

    const fullPath = path.join(PUBLIC_DIR, filepath);
    // Safety: only allow deletion within public folder
    if (!fullPath.startsWith(PUBLIC_DIR)) {
      return res.json({ success: false, message: 'Invalid path' });
    }

    await fs.unlink(fullPath);
    res.json({ success: true, message: 'File deleted' });
  } catch (err) {
    res.json({ success: false, message: err.message });
  }
});

// Create folder
app.post('/api/folders', async (req, res) => {
  try {
    const { folderPath } = req.body;
    if (!folderPath) {
      return res.json({ success: false, message: 'No folder path provided' });
    }

    const fullPath = path.join(PUBLIC_DIR, folderPath);
    await fs.mkdir(fullPath, { recursive: true });
    res.json({ success: true, message: 'Folder created' });
  } catch (err) {
    res.json({ success: false, message: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`\n🚀 CMS running at http://localhost:${PORT}`);
  console.log(`   Data directory: ${DATA_DIR}`);
  console.log(`   Repo directory: ${REPO_DIR}\n`);
});
