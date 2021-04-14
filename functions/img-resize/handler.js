// This image resize function is a modified version of what is shown by [Nic Raboy](https://www.nicraboy.com) of [The Polyglot Developer](https://www.thepolyglotdeveloper.com) [this blog post](https://www.thepolyglotdeveloper.com/2017/12/convert-nodejs-restful-api-serverless-openwhisk/).
// When reproducing, you must add proper attribution within your project, documentation, etc., to the author, site, and exact links as above.
// Permission for reuse from The Polyglot Developer is strictly for the code snippets.
// Please do not copy or modify blog content such as instructive text, images, etc.

const Image = require("./image");

function main(params) {
  const i = new Image(Buffer.from(params.__ow_body, "base64"));
  const res = i.generate();
  const ret_val = res.then(val => {
    val.result = "ok";
    const qs = params.__ow_query;
    const testid = qs.split("&")[0];
    val.testid = testid;
    return val;
  }).catch(err => {
    return {
      statusCode: 500,
      body: err
    };
  });

  return ret_val;
}

exports.main = main;
