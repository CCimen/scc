class SundsvallsClaude < Formula
  include Language::Python::Virtualenv

  desc "Safely run Claude Code with team configurations and worktree management"
  homepage "https://github.com/sundsvalls/claude-code-cli"
  url "https://github.com/sundsvalls/claude-code-cli/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"

  depends_on "python@3.12"

  resource "typer" do
    url "https://files.pythonhosted.org/packages/typer/typer-0.9.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/rich/rich-13.7.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "Sundsvalls", shell_output("#{bin}/scc --help")
  end
end
