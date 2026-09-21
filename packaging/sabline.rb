# Homebrew formula. To publish:
#   1. brew tap-new gowrishankar-infra/sabline
#   2. copy this into Formula/sabline.rb in that tap
#   3. brew install --build-from-source gowrishankar-infra/sabline/sabline
#   4. brew test sabline && brew audit --strict sabline
#
# The sha256 below must match the PyPI tarball for the version; get it
# with: curl -sL <url> | shasum -a 256

class Sabline < Formula
  include Language::Python::Virtualenv

  desc "Language where signatures declare effects and machine-checked promises"
  homepage "https://sabline.dev/"
  url "https://files.pythonhosted.org/packages/source/v/sabline-lang/sabline_lang-2.55.0.tar.gz"
  sha256 "REPLACE_WITH_THE_TARBALL_SHA256"
  license "MIT"

  depends_on "python@3.12"

  resource "z3-solver" do
    url "https://files.pythonhosted.org/packages/source/z/z3-solver/z3_solver-4.13.0.0.tar.gz"
    sha256 "REPLACE_WITH_THE_Z3_SHA256"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    (testpath/"hello.vel").write <<~SABLINE
      fn main() uses io {
          print("hello from a formula")
      }
    SABLINE
    assert_match "hello from a formula",
                 shell_output("#{bin}/sabline #{testpath}/hello.vel")

    # the effect budget must hold in a packaged build too
    (testpath/"peek.vel").write <<~SABLINE
      fn main() uses io, fs {
          write_file("out.txt", "x")
          print("wrote it")
      }
    SABLINE
    output = shell_output("#{bin}/sabline #{testpath}/peek.vel --allow io 2>&1",
                          1)
    assert_match "E310", output

    # ...and it holds with no --allow at all: a run gets io from 5.0,
    # where before it got every effect
    output = shell_output("#{bin}/sabline #{testpath}/peek.vel 2>&1", 1)
    assert_match "E310", output
  end
end
