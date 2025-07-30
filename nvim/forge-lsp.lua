-- Neovim LSP configuration for Forge LSP
-- Place this file in your Neovim configuration directory

local M = {}

-- Configuration for the Forge LSP server
M.setup = function(opts)
  opts = opts or {}

  local default_config = {
    name = "forge-lsp",
    cmd = { "forge-lsp" },
    filetypes = { "solidity" },
    root_dir = function(fname)
      return require("lspconfig.util").root_pattern(
        "foundry.toml",
        "forge.toml",
        "hardhat.config.js",
        "hardhat.config.ts",
        "truffle-config.js",
        "package.json",
        ".git"
      )(fname)
    end,
    settings = {
      forge = {
        -- Enable/disable features
        diagnostics = {
          enable = true,
          onSave = true,
        },
        completion = {
          enable = true,
          triggerCharacters = { ".", "(", " " },
        },
        hover = {
          enable = true,
        },
        -- Foundry-specific settings
        foundry = {
          profile = "default",
          buildOnSave = true,
          testOnSave = false,
        },
      },
    },
    capabilities = require("cmp_nvim_lsp").default_capabilities(),
    on_attach = function(client, bufnr)
      -- Enable completion triggered by <c-x><c-o>
      vim.api.nvim_buf_set_option(bufnr, "omnifunc", "v:lua.vim.lsp.omnifunc")

      -- Mappings
      local bufopts = { noremap = true, silent = true, buffer = bufnr }
      vim.keymap.set("n", "gD", vim.lsp.buf.declaration, bufopts)
      vim.keymap.set("n", "gd", vim.lsp.buf.definition, bufopts)
      vim.keymap.set("n", "K", vim.lsp.buf.hover, bufopts)
      vim.keymap.set("n", "gi", vim.lsp.buf.implementation, bufopts)
      vim.keymap.set("n", "<C-k>", vim.lsp.buf.signature_help, bufopts)
      vim.keymap.set(
        "n",
        "<space>wa",
        vim.lsp.buf.add_workspace_folder,
        bufopts
      )
      vim.keymap.set(
        "n",
        "<space>wr",
        vim.lsp.buf.remove_workspace_folder,
        bufopts
      )
      vim.keymap.set("n", "<space>wl", function()
        print(vim.inspect(vim.lsp.buf.list_workspace_folders()))
      end, bufopts)
      vim.keymap.set("n", "<space>D", vim.lsp.buf.type_definition, bufopts)
      vim.keymap.set("n", "<space>rn", vim.lsp.buf.rename, bufopts)
      vim.keymap.set("n", "<space>ca", vim.lsp.buf.code_action, bufopts)
      vim.keymap.set("n", "gr", vim.lsp.buf.references, bufopts)
      vim.keymap.set("n", "<space>f", function()
        vim.lsp.buf.format({ async = true })
      end, bufopts)

      -- Forge-specific keymaps
      vim.keymap.set("n", "<space>fb", function()
        vim.cmd("!forge build")
      end, { desc = "Forge Build", buffer = bufnr })

      vim.keymap.set("n", "<space>ft", function()
        vim.cmd("!forge test")
      end, { desc = "Forge Test", buffer = bufnr })

      vim.keymap.set("n", "<space>fc", function()
        vim.cmd("!forge clean")
      end, { desc = "Forge Clean", buffer = bufnr })
    end,
  }

  -- Merge user options with defaults
  local config = vim.tbl_deep_extend("force", default_config, opts)

  -- Register the LSP server
  require("lspconfig.configs").forge_lsp = {
    default_config = config,
  }

  -- Start the LSP server
  require("lspconfig").forge_lsp.setup(config)
end

-- Auto-detect Solidity files and set filetype
vim.api.nvim_create_autocmd({ "BufRead", "BufNewFile" }, {
  pattern = "*.sol",
  callback = function()
    vim.bo.filetype = "solidity"
  end,
})

-- Solidity syntax highlighting (basic)
vim.api.nvim_create_autocmd("FileType", {
  pattern = "solidity",
  callback = function()
    -- Set basic syntax highlighting
    vim.cmd([[
      syntax keyword solidityKeyword contract interface library abstract function modifier event struct enum mapping
      syntax keyword solidityKeyword public private internal external pure view payable constant immutable override virtual
      syntax keyword solidityKeyword returns return if else for while do break continue try catch throw revert require assert
      syntax keyword solidityKeyword import pragma using is as memory storage calldata stack
      syntax keyword solidityType address bool string bytes uint int fixed ufixed
      syntax keyword solidityType uint8 uint16 uint32 uint64 uint128 uint256
      syntax keyword solidityType int8 int16 int32 int64 int128 int256
      syntax keyword solidityType bytes1 bytes2 bytes4 bytes8 bytes16 bytes32
      syntax keyword solidityConstant wei gwei ether seconds minutes hours days weeks
      syntax keyword solidityBuiltin msg block tx now
      syntax match solidityNumber '\v<\d+>'
      syntax match solidityAddress '\v0x[a-fA-F0-9]{40}'
      syntax region solidityString start='"' end='"'
      syntax region solidityComment start='//' end='$'
      syntax region solidityComment start='/\*' end='\*/'
      
      highlight link solidityKeyword Keyword
      highlight link solidityType Type
      highlight link solidityConstant Constant
      highlight link solidityBuiltin Function
      highlight link solidityNumber Number
      highlight link solidityAddress Constant
      highlight link solidityString String
      highlight link solidityComment Comment
    ]])
  end,
})

return M
