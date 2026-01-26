const express = require('express');
const cors = require('cors');
const fs = require('fs').promises;
const path = require('path');
const simpleGit = require('simple-git');

const app = express();
const PORT = 3333;

// Paths
const DATA_DIR = path.join(__dirname, '..', 'src', 'data');
const REPO_DIR = path.join(__dirname, '..');
const git = simpleGit(REPO_DIR);

app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, 'public')));

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

app.listen(PORT, () => {
  console.log(`\n🚀 CMS running at http://localhost:${PORT}`);
  console.log(`   Data directory: ${DATA_DIR}`);
  console.log(`   Repo directory: ${REPO_DIR}\n`);
});
