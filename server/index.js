const express = require("express");
const cors = require("cors")
const dotenv = require("dotenv");
const { generateToken } = require("./utils/generateToken");
const { pool } = require("./config/db");
const app = express();

// const authRoutes = require('./routes/auth.routes') 

dotenv.config()
app.use(express.json())
app.use(cors())

app.get("/", (req, res) => {
    res.send("Hello World!");
});

app.get("/token",(req,res)=>{
    const token = generateToken("Manyam Puli")
    return res.json({token:token});
}); //Demo route

pool.query("SELECT NOW()")
  .then(res => console.log("DB Connected:", res.rows[0]))
  .catch(err => console.error("DB Error:", err));

// app.use("/api/auth", authRoutes);

app.listen(process.env.PORT || 3000, () => {
    console.log(`Server is running on port ${process.env.PORT || 3000}`);
});