import { glob } from 'glob';
import { readFile } from 'node:fs/promises';
import { parse } from '@swc/core';
import { extname } from 'node:path';

/**
 * Represents a found hardcoded string with its location information.
 */
const isUrlOrPath = (text) => /^(https|http|\/\/|^\/)/.test(text);

/**
 * Analyzes an AST to find potentially hardcoded strings that should be translated.
 */
function findHardcodedStrings(ast, code, config) {
  const issues = [];
  const nodesToLint = [];

  const getLineNumber = (pos) => {
    return code.substring(0, pos).split('\n').length;
  };

  const transComponents = config.extract?.transComponents || ['Trans'];
  const defaultIgnoredAttributes = ['className', 'key', 'id', 'style', 'href', 'i18nKey', 'defaults', 'type', 'target'];
  const defaultIgnoredTags = ['script', 'style', 'code'];
  const customIgnoredTags = config.extract?.ignoredTags || [];
  const allIgnoredTags = new Set([...transComponents, ...defaultIgnoredTags, ...customIgnoredTags]);
  const customIgnoredAttributes = config.extract?.ignoredAttributes || [];
  const ignoredAttributes = new Set([...defaultIgnoredAttributes, ...customIgnoredAttributes]);

  // Helper: robustly extract a JSX element name from different node shapes
  const extractJSXName = (node) => {
    if (!node) return null;
    const nameNode = node.name ?? node.opening?.name ?? node.opening?.name;
    if (!nameNode) {
      if (node.opening?.name) return extractJSXName({ name: node.opening.name });
      return null;
    }

    const fromIdentifier = (n) => {
      if (!n) return null;
      if (n.type === 'JSXIdentifier' && (n.name || n.value)) return (n.name ?? n.value);
      if (n.type === 'Identifier' && (n.name || n.value)) return (n.name ?? n.value);
      if (n.type === 'JSXMemberExpression') {
        const object = fromIdentifier(n.object);
        const property = fromIdentifier(n.property);
        return object && property ? `${object}.${property}` : (property ?? object);
      }
      return n.name ?? n.value ?? n.property?.name ?? n.property?.value ?? null;
    };

    return fromIdentifier(nameNode);
  };

  // Helper: return true if any JSX ancestor is in the ignored tags set
  const isWithinIgnoredElement = (ancestors) => {
    for (let i = ancestors.length - 1; i >= 0; i--) {
      const an = ancestors[i];
      if (!an || typeof an !== 'object') continue;
      if (an.type === 'JSXElement' || an.type === 'JSXOpeningElement' || an.type === 'JSXSelfClosingElement') {
        const name = extractJSXName(an);
        if (name && allIgnoredTags.has(name)) return true;
      }
    }
    return false;
  };

  // --- PHASE 1: Collect all potentially problematic nodes ---
  const walk = (node, ancestors) => {
    if (!node || typeof node !== 'object') return;

    const currentAncestors = [...ancestors, node];

    if (node.type === 'JSXText') {
      const isIgnored = isWithinIgnoredElement(currentAncestors);

      if (!isIgnored) {
        const text = node.value.trim();
        // Filter out: empty strings, single chars, URLs, numbers, interpolations, and ellipsis
        if (text && text.length > 1 && text !== '...' && !isUrlOrPath(text) && isNaN(Number(text)) && !text.startsWith('{{')) {
          nodesToLint.push(node);
        }
      }
    }

    if (node.type === 'StringLiteral') {
      const parent = currentAncestors.length >= 2 ? currentAncestors[currentAncestors.length - 2] : null;
      const insideIgnored = isWithinIgnoredElement(currentAncestors);

      // Check if it's a JSX attribute
      if (parent?.type === 'JSXAttribute' && !ignoredAttributes.has(parent.name.value) && !insideIgnored) {
        const text = node.value.trim();
        // Filter out: empty strings, URLs, numbers, and ellipsis
        if (text && text !== '...' && !isUrlOrPath(text) && isNaN(Number(text))) {
          nodesToLint.push(node);
        }
      }
      // Also check for regular string literals (not just JSX attributes)
      // This will catch hardcoded strings in regular JS/TS code
      else if (!insideIgnored && parent?.type !== 'JSXAttribute') {
        const text = node.value.trim();
        // Filter out: empty strings, single chars, URLs, numbers, interpolation, ellipsis
        // Also filter out common patterns like imports, requires, etc.
        if (text && text.length > 1 && text !== '...' && !isUrlOrPath(text) && isNaN(Number(text)) && !text.startsWith('{{')) {
          // Check if parent is import/require statement (these are usually not user-facing strings)
          const isImportLike = parent?.type === 'ImportDeclaration' || 
                               parent?.type === 'CallExpression' && parent.callee?.type === 'Identifier' && 
                               (parent.callee.name === 'require' || parent.callee.name === 'import');
          
          if (!isImportLike) {
            nodesToLint.push(node);
          }
        }
      }
    }

    // Recurse into children
    for (const key of Object.keys(node)) {
      if (key === 'span') continue;
      const child = node[key];
      if (Array.isArray(child)) {
        child.forEach(item => walk(item, currentAncestors));
      } else if (child && typeof child === 'object') {
        walk(child, currentAncestors);
      }
    }
  };

  walk(ast, []);

  // --- PHASE 2: Find line numbers using a tracked search on the raw source code ---
  let lastSearchIndex = 0;
  for (const node of nodesToLint) {
    const searchText = node.raw ?? node.value;

    const position = code.indexOf(searchText, lastSearchIndex);

    if (position > -1) {
      issues.push({
        text: node.value.trim(),
        line: getLineNumber(position),
      });
      lastSearchIndex = position + searchText.length;
    }
  }

  return issues;
}

/**
 * Main function to parse files and find hardcoded strings
 */
async function parseFiles(inputPatterns, ignorePatterns, config) {
  const defaultIgnore = ['node_modules/**'];
  const userIgnore = Array.isArray(ignorePatterns)
    ? ignorePatterns
    : ignorePatterns ? [ignorePatterns] : [];

  const allIgnore = [...defaultIgnore, ...userIgnore];
  const inputPatternsArray = Array.isArray(inputPatterns) ? inputPatterns : [inputPatterns];

  // Use Set to deduplicate files
  const sourceFilesSet = new Set();
  for (const pattern of inputPatternsArray) {
    const files = await glob(pattern, { ignore: allIgnore });
    files.forEach(file => sourceFilesSet.add(file));
  }
  const sourceFiles = Array.from(sourceFilesSet);
  
  // Log files found for debugging
  if (sourceFiles.length === 0) {
    // Output error to stderr, result to stdout
    const result = {
      success: true,
      message: `No files found matching patterns: ${inputPatternsArray.join(', ')}`,
      files: {},
      totalIssues: 0
    };
    console.log(JSON.stringify(result));
    return result;
  }

  const issuesByFile = {};
  let totalIssues = 0;
  
  // Debug: log files found (to stderr so it doesn't interfere with stdout)
  if (process.env.VERBOSE === 'true') {
    console.error(JSON.stringify({ debug: `Found ${sourceFiles.length} files to process` }));
    if (sourceFiles.length > 0) {
      console.error(JSON.stringify({ debug: `Files: ${sourceFiles.slice(0, 5).join(', ')}${sourceFiles.length > 5 ? '...' : ''}` }));
    }
  }

  for (const file of sourceFiles) {
    try {
      const code = await readFile(file, 'utf-8');

      // Determine parser options from file extension
      const fileExt = extname(file).toLowerCase();
      const isTypeScriptFile = fileExt === '.ts' || fileExt === '.tsx' || fileExt === '.mts' || fileExt === '.cts';
      const isTSX = fileExt === '.tsx';

      let ast;
      try {
        ast = await parse(code, {
          syntax: isTypeScriptFile ? 'typescript' : 'ecmascript',
          tsx: isTSX,
          decorators: true
        });
      } catch (err) {
        // Some projects use JSX/TSX in .ts files. Try fallback parse with tsx:true
        if (fileExt === '.ts' && !isTSX) {
          try {
            ast = await parse(code, {
              syntax: 'typescript',
              tsx: true,
              decorators: true
            });
          } catch (err2) {
          // Log parse errors to stderr, but continue processing
          if (process.env.VERBOSE === 'true') {
            console.error(JSON.stringify({ debug: `Failed to parse ${file}: ${err2.message}` }));
          }
          continue;
        }
      } else {
        // Log parse errors to stderr, but continue processing
        if (process.env.VERBOSE === 'true') {
          console.error(JSON.stringify({ debug: `Failed to parse ${file}: ${err.message}` }));
        }
        continue;
      }
      }

      const hardcodedStrings = findHardcodedStrings(ast, code, config);

      if (hardcodedStrings.length > 0) {
        totalIssues += hardcodedStrings.length;
        issuesByFile[file] = hardcodedStrings;
        // Debug: log issues found (to stderr so it doesn't interfere with stdout)
        if (process.env.VERBOSE === 'true') {
          console.error(JSON.stringify({ debug: `Found ${hardcodedStrings.length} issues in ${file}` }));
        }
      }
    } catch (error) {
      // Log errors to stderr, but continue processing
      if (process.env.VERBOSE === 'true') {
        console.error(JSON.stringify({ debug: `Error processing ${file}: ${error.message}` }));
      }
    }
  }

  const result = {
    success: totalIssues === 0,
    message: totalIssues > 0 ? `Linter found ${totalIssues} potential issues.` : 'No issues found.',
    files: issuesByFile,
    totalIssues
  };
  
  // Debug: Print result to verify it's correct
  if (process.env.VERBOSE === 'true') {
    console.error(JSON.stringify({ debug: `Result: ${totalIssues} total issues in ${Object.keys(issuesByFile).length} files` }));
    for (const [file, issues] of Object.entries(issuesByFile)) {
      console.error(JSON.stringify({ debug: `File ${file}: ${issues.length} issues` }));
    }
  }
  
  return result;
}

// CLI entry point
const args = process.argv.slice(2);
if (args.length < 1) {
  console.error('Usage: node js_parser.js <input_patterns> [ignore_patterns] [config_json]');
  process.exit(1);
}

const inputPatterns = JSON.parse(args[0]);
const ignorePatterns = args[1] ? JSON.parse(args[1]) : [];
const config = args[2] ? JSON.parse(args[2]) : { extract: {} };

parseFiles(inputPatterns, ignorePatterns, config)
  .then(result => {
    // Output result to stdout ONLY - this is the only thing that should be on stdout
    // Make sure it's on a single line and properly formatted
    const output = JSON.stringify(result);
    console.log(output);
    // Exit with code 0 if no issues found, 1 if issues found
    // (success=false means issues were found, which is good - we want to report them)
    process.exit(0);
  })
  .catch(error => {
    // Errors go to stdout as JSON result (not stderr, so Python can parse it)
    const errorResult = { error: error.message, success: false, files: {}, totalIssues: 0, message: `Error: ${error.message}` };
    console.log(JSON.stringify(errorResult));
    process.exit(1);
  });

