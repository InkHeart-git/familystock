/**
 * Human-like interaction utilities for anti-detection
 * Simulates real user behavior with random delays, mouse movements, and typing patterns
 */

const { randomInt } = require('crypto');

/**
 * Random delay between min and max milliseconds
 */
async function humanDelay(min = 1000, max = 3000) {
  const delay = randomInt(Math.floor(min), Math.floor(max));
  await new Promise(resolve => setTimeout(resolve, delay));
}

/**
 * Simulate human "thinking" pause before important actions
 */
async function humanThink(min = 2000, max = 4000) {
  await humanDelay(min, max);
}

/**
 * Simulate reading/browsing a page with random scroll and mouse movement
 */
async function humanBrowse(page, options = {}) {
  const { duration = 3000, scrollChance = 0.7 } = options;
  const startTime = Date.now();
  
  while (Date.now() - startTime < duration) {
    // Random scroll
    if (Math.random() < scrollChance) {
      const scrollAmount = randomInt(Math.floor(-300), Math.floor(300));
      await page.evaluate(([amount]) => window.scrollBy(0, amount), [scrollAmount]);
    }
    
    // Random mouse movement
    const x = randomInt(Math.floor(100), Math.floor(800));
    const y = randomInt(Math.floor(100), Math.floor(600));
    await page.mouse.move(x, y);
    
    await humanDelay(500, 1500);
  }
}

/**
 * Simulate human scrolling behavior
 */
async function humanScroll(page, options = {}) {
  const { direction = 'down', amount = 500 } = options;
  const scrollAmount = direction === 'down' ? amount : -amount;
  
  // Multiple small scrolls instead of one big jump
  const steps = randomInt(Math.floor(3), Math.floor(6));
  const stepAmount = scrollAmount / steps;
  
  for (let i = 0; i < steps; i++) {
    await page.evaluate(([amt]) => window.scrollBy(0, amt), [stepAmount]);
    await humanDelay(200, 500);
  }
}

/**
 * Simulate human click with bezier curve mouse movement
 */
async function humanClick(page, selector, options = {}) {
  const { hoverDelay = [500, 1500] } = options;
  
  // Find element
  const element = await page.waitForSelector(selector, { timeout: 10000 });
  if (!element) throw new Error(`Element not found: ${selector}`);
  
  // Get element position
  const box = await element.boundingBox();
  if (!box) throw new Error(`Element not visible: ${selector}`);
  
  // Calculate target position (random point within element)
  const targetX = box.x + randomInt(Math.floor(5), Math.floor(Math.max(6, Math.floor(box.width - 5))));
  const targetY = box.y + randomInt(Math.floor(5), Math.floor(Math.max(6, Math.floor(box.height - 5))));
  
  // Get current mouse position
  const currentPos = await page.evaluate(() => ({
    x: window.mouseX || 0,
    y: window.mouseY || 0
  }));
  
  // Bezier curve movement
  const startX = currentPos.x || randomInt(Math.floor(100), Math.floor(500));
  const startY = currentPos.y || randomInt(Math.floor(100), Math.floor(500));
  
  const controlX = (startX + targetX) / 2 + randomInt(Math.floor(-100), Math.floor(100));
  const controlY = (startY + targetY) / 2 + randomInt(Math.floor(-100), Math.floor(100));
  
  const steps = randomInt(Math.floor(10), Math.floor(20));
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const x = (1 - t) * (1 - t) * startX + 2 * (1 - t) * t * controlX + t * t * targetX;
    const y = (1 - t) * (1 - t) * startY + 2 * (1 - t) * t * controlY + t * t * targetY;
    await page.mouse.move(x, y);
    await humanDelay(10, 30);
  }
  
  // Hover before click
  await humanDelay(...hoverDelay);
  
  // Click with random offset
  await page.mouse.down();
  await humanDelay(50, 150);
  await page.mouse.up();
  
  // Update tracked position
  await page.evaluate(([x, y]) => {
    window.mouseX = x;
    window.mouseY = y;
  }, [targetX, targetY]);
}

/**
 * Simulate human typing with character-by-character input and occasional typos
 */
async function humanType(page, selector, text, options = {}) {
  const { typoRate = 0.03, speedVariation = 0.3 } = options;
  
  const element = await page.waitForSelector(selector, { timeout: 10000 });
  if (!element) throw new Error(`Element not found: ${selector}`);
  
  // Focus element
  await element.click();
  await humanDelay(100, 300);
  
  // Clear existing content
  await element.fill('');
  await humanDelay(200, 400);
  
  // Type character by character
  const chars = text.split('');
  for (let i = 0; i < chars.length; i++) {
    const char = chars[i];
    
    // Simulate typo (3% chance)
    if (Math.random() < typoRate && i > 0) {
      const wrongChar = String.fromCharCode(char.charCodeAt(0) + randomInt(Math.floor(-2), Math.floor(2)));
      await element.type(wrongChar, { delay: randomInt(Math.floor(50), Math.floor(150)) });
      await humanDelay(200, 400);
      
      // Backspace to correct
      await page.keyboard.press('Backspace');
      await humanDelay(200, 400);
    }
    
    // Type correct character
    const baseDelay = randomInt(Math.floor(80), Math.floor(150));
    const variedDelay = baseDelay * (1 + (Math.random() - 0.5) * speedVariation);
    await element.type(char, { delay: Math.max(30, variedDelay) });
    
    // Random pause between words
    if (char === ' ' || char === ',' || char === '.') {
      await humanDelay(150, 400);
    }
  }
  
  // Pause after typing
  await humanDelay(300, 800);
}

/**
 * Fill contenteditable div (for rich text editors)
 */
async function humanFillContentEditable(page, selector, text) {
  const element = await page.waitForSelector(selector, { timeout: 10000 });
  if (!element) throw new Error(`Element not found: ${selector}`);
  
  await element.click();
  await humanDelay(200, 500);
  
  // Clear and type
  await page.evaluate(([sel]) => {
    const el = document.querySelector(sel);
    if (el) el.innerHTML = '';
  }, [selector]);
  
  await humanDelay(200, 400);
  
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    await page.keyboard.type(lines[i], { delay: randomInt(Math.floor(50), Math.floor(100)) });
    if (i < lines.length - 1) {
      await page.keyboard.press('Enter');
      await humanDelay(200, 500);
    }
  }
}

/**
 * Random wait for cron tasks (in minutes)
 */
async function jitterWait(minMinutes = 1, maxMinutes = 10) {
  const delayMs = randomInt(Math.floor(minMinutes * 60000), Math.floor(maxMinutes * 60000));
  await new Promise(resolve => setTimeout(resolve, delayMs));
}

module.exports = {
  humanDelay,
  humanThink,
  humanBrowse,
  humanScroll,
  humanClick,
  humanType,
  humanFillContentEditable,
  jitterWait
};
