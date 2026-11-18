class Keelway < Formula
  include Language::Python::Virtualenv

  desc "Customer-managed hybrid AI governance, MCP control plane, and multi-agent platform"
  homepage "https://github.com/creova-gif/keelway"
  url "https://github.com/creova-gif/keelway.git", tag: "v1.1.0"
  license "Apache-2.0"
  head "https://github.com/creova-gif/keelway.git", branch: "main"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/keelway", "--help"
  end
end
